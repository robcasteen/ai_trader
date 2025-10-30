import logging
import json
import os
from pathlib import Path
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from app.data_collector import data_collector
from app.risk_manager import risk_manager

# --- Configure logging early so our INFO lines always show
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# --- Dashboard (UI) ---
from app.dashboard import router as dashboard_router

# --- Trading logic ---
from app.logic.sentiment import SentimentSignal
from app.logic.paper_trader import PaperTrader
from app.logic.notifier import Notifier
from app.logic.symbol_scanner import get_top_symbols
from app.news_fetcher import get_unseen_headlines, mark_as_seen
from app.client.kraken import KrakenClient
from app.config import get_current_config

# --- Core bot components ---
client = KrakenClient()
kraken = KrakenClient()
signal_model = SentimentSignal()
trader = PaperTrader()
notifier = Notifier()

# --- State tracking ---
PROJECT_ROOT = Path(__file__).resolve().parent  # /src
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
# REMOVED: STATUS_FILE - status now tracked in database

# --- FastAPI app ---
app = FastAPI(title="Trading Bot Dashboard")

# Mount static files
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT_STATIC = Path(__file__).resolve().parents[1]  # /src
app.mount(
    "/static", StaticFiles(directory=str(PROJECT_ROOT_STATIC / "static")), name="static"
)

# Mount the dashboard UI routes
app.include_router(dashboard_router)


# REMOVED: save_status_to_file - status is now tracked in database only


def normalize_symbol(sym: str) -> str:
    """Ensure 'BTCUSD' -> 'BTC/USD' for price/trade consistency."""
    if "/" in sym:
        return sym
    if len(sym) > 3:
        base, quote = sym[:-3], sym[-3:]
        return f"{base}/{quote}"
    return sym


def run_trade_cycle():
    """Run one trade evaluation cycle with multi-strategy analysis."""
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"[TradeCycle] === Starting cycle at {start_time} ===")

    # CHECK RISK MANAGER FIRST - ADDED
    if not risk_manager.can_trade():
        msg = "Risk manager blocked trading (daily loss limit reached)"
        logging.error(f"[TradeCycle] {msg}")
        return

    # Initialize strategy manager with correct logs directory
    from app.strategies.strategy_manager import StrategyManager
    from pathlib import Path
    from app.database.connection import get_db
    from app.database.repositories import BotConfigRepository

    # Load configuration from database
    try:
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            strategy_config = config_repo.get_config_dict()
            strategy_config["logs_dir"] = str(LOGS_DIR)  # Add logs directory
            logging.info(f"[TradeCycle] Loaded config from database: min_confidence={strategy_config.get('min_confidence')}")
    except Exception as e:
        logging.error(f"[TradeCycle] Failed to load config from database, using defaults: {e}")
        # Fallback to defaults
        strategy_config = {
            "use_technical": True,
            "use_volume": True,
            "min_confidence": 0.5,
            "aggregation_method": "weighted_vote",
            "logs_dir": str(LOGS_DIR),
        }

    strategy_manager = StrategyManager(config=strategy_config)

    # Fetch scanner symbols and unseen headlines
    symbols = get_top_symbols(limit=10)
    headlines_by_symbol = get_unseen_headlines()

    logging.info(f"[Scanner] Top {len(symbols)} symbols: {symbols}")
    logging.info(
        f"[News] Retrieved {len(headlines_by_symbol)} symbol groups with unseen headlines"
    )

    # Combine symbols from scanner and news
    all_symbols = set(symbols)
    all_symbols.update(headlines_by_symbol.keys())

    # Normalize symbols to prevent duplicates (BTC/USD vs BTCUSD)
    # Keep the slash format as canonical
    normalized_symbols = set()
    symbol_map = {}  # Map normalized -> original for news lookup

    for symbol in all_symbols:
        # Normalize by removing slash
        normalized = symbol.replace("/", "")

        # Keep the first version we see (prefer slashed version)
        if normalized not in symbol_map or "/" in symbol:
            symbol_map[normalized] = symbol
            normalized_symbols.add(symbol if "/" in symbol else symbol)

    all_symbols = normalized_symbols
    if not all_symbols:
        # Fallback to default tracked symbols
        all_symbols = {"BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "DOGEUSD"}
        logging.info("[TradeCycle] No scanner/news symbols, using fallback list")

    # Process each symbol
    for symbol in all_symbols:
        logging.info(f"[{symbol}] Checking...")

        try:
            # Get current price
            price = client.get_price(symbol)
            logging.info(f"[{symbol}] Current price: {price}")

            # ADDED - Skip if invalid price
            if price <= 0:
                logging.warning(f"[{symbol}] Invalid price, skipping")
                continue

            # Get current balance (ZUSD asset for paper trading)
            balance = client.get_balance(asset="ZUSD")
            logging.info(f"[{symbol}] Current USD balance: {balance}")

            # ADDED - Calculate position size from risk manager
            amount = risk_manager.calculate_position_size(price, balance)
            logging.info(f"[{symbol}] Risk-adjusted position size: {amount}")

            # Prepare context for strategies - UPDATED WITH DATA COLLECTOR
            context = {
                "headlines": headlines_by_symbol.get(symbol, []),
                "price": price,
                "symbol": symbol,
                "price_history": data_collector.get_price_history(
                    symbol, limit=50
                ),  # CHANGED
                "volume_history": data_collector.get_volume_history(
                    symbol, limit=50
                ),  # CHANGED
            }

            # ADDED - Add current volume
            vol_hist = data_collector.get_volume_history(symbol, limit=1)
            context["volume"] = vol_hist[-1] if vol_hist else 0

            # Get aggregated signal from all strategies (now returns signal_id)
            signal, confidence, reason, signal_id = strategy_manager.get_signal(symbol, context)

            logging.info(f"[{symbol}] Signal: {signal} | Reason: {reason} | Signal ID: {signal_id}")

            # Execute trade based on signal - UPDATED WITH RISK-MANAGED AMOUNT AND SIGNAL_ID
            result = trader.execute_trade(
                symbol=symbol,
                action=signal,
                price=price,
                balance=balance,
                reason=reason,
                amount=amount,  # CHANGED - use risk-managed amount instead of default
                signal_id=signal_id,  # Link trade to the signal that triggered it
            )

            logging.info(f"[{symbol}] Trade result: {result}")

            # Send notification
            notifier.send(result)

            logging.info(f"[{symbol}] Notified result.")

            # Mark headlines as seen
            if symbol in headlines_by_symbol:
                mark_as_seen(headlines_by_symbol[symbol])
                logging.info(
                    f"[{symbol}] Marked {len(headlines_by_symbol[symbol])} headlines as seen."
                )

        except Exception as e:
            logging.error(f"[{symbol}] Error processing: {e}")
            continue

    # Trade cycle complete
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"[TradeCycle] === Completed cycle at {end_time} === Processed {len(all_symbols)} symbols")

    # Emit BOT_STATUS_CHANGED event to notify UI
    try:
        import asyncio
        from app.events.event_bus import event_bus, EventType
        from datetime import timezone

        asyncio.run(event_bus.emit(EventType.BOT_STATUS_CHANGED, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle_complete": True,
            "symbols_processed": len(all_symbols)
        }))
        logging.debug("[TradeCycle] Emitted BOT_STATUS_CHANGED event")
    except Exception as e:
        logging.error(f"[TradeCycle] Failed to emit BOT_STATUS_CHANGED event: {e}")


def get_next_run_time():
    """Calculate next scheduled run time."""
    from datetime import datetime, timedelta

    next_run = datetime.now() + timedelta(minutes=5)
    return next_run.strftime("%Y-%m-%d %H:%M:%S")


# --- Scheduler setup ---
scheduler = BackgroundScheduler()


# Add proper signal handling for graceful shutdown
import signal
import sys

def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logging.info(f"[Shutdown] Received signal {signum}")
    
    # Stop data collector
    try:
        data_collector.stop()
        logging.info("[Shutdown] Data collector stopped")
    except Exception as e:
        logging.error(f"[Shutdown] Error stopping data collector: {e}")
    
    # Stop scheduler
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logging.info("[Shutdown] Scheduler stopped")
    except Exception as e:
        logging.error(f"[Shutdown] Error stopping scheduler: {e}")
    
    logging.info("[Shutdown] Complete")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)   # Ctrl+C
signal.signal(signal.SIGTERM, handle_shutdown)  # kill command

logging.info("[Startup] Signal handlers registered")

@app.on_event("startup")
def start_scheduler():
    logging.info("[Startup] FastAPI app is launching...")

    # If we're under pytest, don't start the scheduler (prevents background writes during tests)
    if os.environ.get("PYTEST_CURRENT_TEST"):
        logging.info("[Startup] Detected pytest environment; scheduler will NOT start.")
        logging.info(
            "[Startup] Application startup complete. Ready to accept requests."
        )
        return

    # ADDED - Start data collector FIRST
    data_collector.start()
    logging.info("[Startup] Data collector started")

    if not scheduler.running:
        trigger = IntervalTrigger(minutes=5)
        job = scheduler.add_job(
            run_trade_cycle, trigger, id="trade_cycle", replace_existing=True
        )
        scheduler.start()
        logging.info(
            "[Startup] Scheduler started. Trade cycle scheduled every 5 minutes."
        )
        logging.info(f"[Startup] Next scheduled run at: {job.next_run_time}")

    # IMPORTANT: Do NOT run an immediate cycle here.
    logging.info("[Startup] Application startup complete. Ready to accept requests.")


@app.on_event("shutdown")
def shutdown_scheduler():
    # ADDED - Stop data collector
    data_collector.stop()
    logging.info("[Shutdown] Data collector stopped")

    if scheduler.running:
        scheduler.shutdown()
        logging.info("[Shutdown] Scheduler shutdown complete.")


# --- Manual trigger endpoint ---
@app.get("/run-now")
def run_now():
    logging.info("[Manual] Trade cycle triggered via /run-now endpoint")
    run_trade_cycle()

    job = scheduler.get_job("trade_cycle")
    next_run = (
        job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        if job and job.next_run_time
        else "Unknown"
    )

    return {
        "status": "ok",
        "message": "Trade cycle executed",
        "next_run": next_run,
    }


# --- Bot status endpoint ---
@app.get("/status")
def get_status():
    """Expose bot's last run status for the dashboard - loads from database."""
    from datetime import timezone

    # Get next run time from scheduler (already in local time)
    next_run_time = None
    try:
        job = scheduler.get_job("trade_cycle")
        if job and job.next_run_time:
            next_run_time = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logging.warning(f"[Status] Failed to get next run time from scheduler: {e}")

    try:
        from app.database.connection import get_db
        from app.database.repositories import BotConfigRepository, SignalRepository

        with get_db() as db:
            config_repo = BotConfigRepository(db)
            signal_repo = SignalRepository(db)

            config = config_repo.get_current()

            # Get last run time from most recent signal (UTC in DB, convert to local)
            last_run_time = None
            recent_signals = signal_repo.get_recent(hours=24, test_mode=False, limit=1)
            if recent_signals:
                signal_ts = recent_signals[0].timestamp
                # If naive, assume UTC
                if signal_ts.tzinfo is None:
                    signal_ts = signal_ts.replace(tzinfo=timezone.utc)
                # Convert to local time
                local_ts = signal_ts.astimezone()
                last_run_time = local_ts.strftime("%Y-%m-%d %H:%M:%S")

            if config:
                return {
                    "last_status": {
                        "time": last_run_time,
                        "message": f"Mode: {config.mode}, Min Confidence: {config.min_confidence}",
                        "next_run": next_run_time,
                    },
                    "next_run": next_run_time
                }
    except Exception as e:
        logging.error(f"[Status] Failed to load status from database: {e}")

    # No config found
    return {
        "last_status": {
            "time": None,
            "message": "No configuration found in database",
            "next_run": next_run_time,
        },
        "next_run": next_run_time
    }
