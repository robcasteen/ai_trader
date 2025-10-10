import logging
import json
import os
from pathlib import Path
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

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
kraken = KrakenClient()
signal_model = SentimentSignal()
trader = PaperTrader()
notifier = Notifier()

# --- State tracking ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # /src
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE = LOGS_DIR / "bot_status.json"

# Initialize in-memory last status (diagnostic only; never returned by /status unless /run-now is called)
last_status = {"time": None, "message": "Bot has not run yet.", "next_run": "Unknown"}

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


def save_status_to_file(status: dict):
    """Persist bot status to logs/bot_status.json and keep memory in sync."""
    global last_status
    last_status = status
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)
        logging.info(f"[Status] Updated bot_status.json: {status}")
    except Exception as e:
        logging.error(f"[Status] Failed to write status file: {e}")


def normalize_symbol(sym: str) -> str:
    """Ensure 'BTCUSD' -> 'BTC/USD' for price/trade consistency."""
    if "/" in sym:
        return sym
    if len(sym) > 3:
        base, quote = sym[:-3], sym[-3:]
        return f"{base}/{quote}"
    return sym


def run_trade_cycle():
    """Run one trade evaluation cycle with detailed logging."""
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"[TradeCycle] === Starting cycle at {start_time} ===")

    config = get_current_config()
    strategy = config.get("strategy", "gpt-sentiment")

    # Normalize "gpt" -> "gpt-sentiment"
    if strategy == "gpt":
        logging.info('[Config] Normalized strategy "gpt" -> "gpt-sentiment"')
        strategy = "gpt-sentiment"

    if strategy != "gpt-sentiment":
        msg = f"Unknown strategy {strategy}"
        logging.warning(f"[Strategy] {msg}")
        save_status_to_file({"time": start_time, "message": msg, "next_run": "Unknown"})
        return

    logging.info(f"[Strategy] Using strategy: {strategy}")

    # Fetch scanner symbols and unseen headlines
    symbols = get_top_symbols(limit=10)
    headlines_by_symbol = get_unseen_headlines()

    logging.info(f"[Scanner] Top {len(symbols)} symbols: {symbols}")
    logging.info(
        f"[News] Retrieved {len(headlines_by_symbol)} symbol groups with unseen headlines"
    )

    # If the scanner returns nothing, still process what news gave us
    if not symbols:
        symbols = list(headlines_by_symbol.keys())

    processed_any = False

    for raw_symbol in symbols:
        sym = normalize_symbol(raw_symbol)
        logging.info(f"[{sym}] Checking...")

        # Headlines for this symbol (work with either 'BTCUSD' or 'BTC/USD' keys)
        sym_variants = {raw_symbol, raw_symbol.replace("/", ""), sym.replace("/", "")}
        sym_headlines = []
        for key in sym_variants:
            sym_headlines.extend(headlines_by_symbol.get(key, []))

        price = kraken.get_price(sym)
        balance = kraken.get_balance("ZUSD")

        logging.info(f"[{sym}] Current price: {price}")
        logging.info(f"[{sym}] Current USD balance: {balance}")

        if not sym_headlines:
            logging.info(f"[{sym}] No new headlines, skipping.")
            continue

        processed_any = True

        # Process each unseen headline independently
        for headline in sym_headlines:
            logging.info(f"[{sym}] Headline: {headline}")

            signal, reason = signal_model.get_signal(headline, sym)
            logging.info(f"[{sym}] Signal: {signal} | Reason: {reason}")

            trade_result = trader.execute_trade(sym, signal, price, balance, reason)
            logging.info(f"[{sym}] Trade result: {trade_result}")

            notifier.send(trade_result)
            logging.info(f"[{sym}] Notified result.")

        # Mark all processed as seen
        try:
            mark_as_seen(raw_symbol, sym_headlines)
        except TypeError:
            # Legacy signature fallback
            for _ in sym_headlines:
                try:
                    mark_as_seen(raw_symbol)
                    break
                except Exception:
                    pass
        logging.info(f"[{sym}] Marked {len(sym_headlines)} headlines as seen.")

    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        "Completed trade cycle successfully."
        if processed_any
        else "No actionable headlines or symbols."
    )
    logging.info(f"[TradeCycle] === Completed cycle at {end_time} ===")

    job = scheduler.get_job("trade_cycle")
    next_run = (
        job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        if job and job.next_run_time
        else "Unknown"
    )

    # Persist full status with next_run
    status = {"time": end_time, "message": msg, "next_run": next_run}
    save_status_to_file(status)

    if job and job.next_run_time:
        logging.info(f"[Scheduler] Next run scheduled at {next_run}")


# --- Scheduler setup ---
scheduler = BackgroundScheduler()


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
        "last_status": last_status,
        "next_run": next_run,  # keep top-level next_run for callers/tests
    }


# --- Bot status endpoint ---
@app.get("/status")
def get_status():
    """Expose bot's last run status for the dashboard.

    Test-friendly behavior:
    - Always attempt to read the *current* STATUS_FILE (patched path during tests).
    - If reading fails, return a deterministic payload.
    """
    try:
        with open(STATUS_FILE, "r") as f:
            status = json.load(f)
        # Always return the file contents; never fall back to in-memory status here
        return {"last_status": status}
    except Exception as e:
        logging.error(f"[Status] Failed to read status file {STATUS_FILE}: {e}")

    # File missing or unreadable: return deterministic payload (no in-memory fallback)
    return {
        "last_status": {
            "time": None,
            "message": "No status file found",
            "next_run": "Unknown",
        }
    }
