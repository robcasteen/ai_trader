from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from collections import defaultdict
from typing import Dict, Any, List, Tuple
import json
import logging
from app.strategy_signal_logger import StrategySignalLogger
from datetime import datetime, timezone

router = APIRouter()


# === Paths ===
PROJECT_ROOT = Path(__file__).resolve().parent  # /src
TEMPLATES_DIR = PROJECT_ROOT.parent / "templates"  # src/templates
LOGS_DIR = PROJECT_ROOT / "logs"

# Initialize strategy signal logger
signal_logger = StrategySignalLogger(data_dir=str(LOGS_DIR))
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ---------- Utilities ----------
def _safe_load_json(p: Path, default):
    try:
        if p.exists():
            with p.open("r") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"[Dashboard] Failed to load {p.name}: {e}")
    return default


def _load_trades() -> List[Dict[str, Any]]:
    trades_file = LOGS_DIR / "trades.json"
    trades = _safe_load_json(trades_file, [])
    if isinstance(trades, list):
        trades.sort(key=lambda t: t.get("timestamp", ""))
    return trades


def _load_status() -> Dict[str, Any]:
    # Single source of truth for status + next_run
    status_file = LOGS_DIR / "bot_status.json"
    data = _safe_load_json(status_file, {"time": None, "message": "Unknown"})
    if not isinstance(data, dict):
        data = {"time": None, "message": "Unknown"}
    # Normalize keys we care about
    if "next_run" not in data:
        data["next_run"] = None
    return data


# ---------- PnL ----------
def load_pnl_data() -> Tuple[List[str], List[float]]:
    trades = _load_trades()
    if not trades:
        return [], []

    pnl_by_symbol = defaultdict(float)
    positions: Dict[str, Dict[str, Any]] = {}
    last_price: Dict[str, float] = {}

    for trade in trades:
        symbol = trade.get("symbol")
        action = (trade.get("action") or "").lower()
        price = trade.get("price")
        amount = trade.get("amount", 0)

        if not symbol or price is None or amount is None:
            continue

        last_price[symbol] = price
        pos = positions.get(symbol)

        if action == "buy":
            if pos is None:
                positions[symbol] = {"price": price, "amount": amount, "side": "long"}
            elif pos["side"] == "long":
                total_cost = pos["price"] * pos["amount"] + price * amount
                total_amount = pos["amount"] + amount
                pos["price"] = (
                    total_cost / total_amount if total_amount else pos["price"]
                )
                pos["amount"] = total_amount
            elif pos["side"] == "short":
                cover_amount = min(amount, pos["amount"])
                pnl = (pos["price"] - price) * cover_amount
                pnl_by_symbol[symbol] += pnl
                pos["amount"] -= cover_amount
                if pos["amount"] <= 0:
                    positions.pop(symbol, None)

        elif action == "sell":
            if pos is None:
                positions[symbol] = {"price": price, "amount": amount, "side": "short"}
            elif pos["side"] == "short":
                total_cost = pos["price"] * pos["amount"] + price * amount
                total_amount = pos["amount"] + amount
                pos["price"] = (
                    total_cost / total_amount if total_amount else pos["price"]
                )
                pos["amount"] = total_amount
            elif pos["side"] == "long":
                sell_amount = min(amount, pos["amount"])
                pnl = (price - pos["price"]) * sell_amount
                pnl_by_symbol[symbol] += pnl
                pos["amount"] -= sell_amount
                if pos["amount"] <= 0:
                    positions.pop(symbol, None)

    for symbol, pos in positions.items():
        if symbol in last_price:
            current_price = last_price[symbol]
            if pos["side"] == "long":
                unrealized = (current_price - pos["price"]) * pos["amount"]
            else:
                unrealized = (pos["price"] - current_price) * pos["amount"]
            pnl_by_symbol[symbol] += unrealized

    labels = list(pnl_by_symbol.keys())
    pnl_data = [round(pnl_by_symbol[s], 2) for s in labels]

    logging.info(f"[PnL] Labels: {labels}")
    logging.info(f"[PnL] Data: {pnl_data}")
    return labels, pnl_data


# ---------- Summary & Sentiment ----------
def build_summary(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "total_trades": 0,
        "buy_count": 0,
        "sell_count": 0,
        "hold_count": 0,  # counted separately, not in total_trades
        "symbols": {},
    }

    if not trades:
        return summary

    labels, pnl_data = load_pnl_data()
    pnl_map = {labels[i]: pnl_data[i] for i in range(len(labels))}

    for t in trades:
        action = (t.get("action") or "").lower()
        symbol = t.get("symbol")
        if not symbol:
            continue

        # HOLDs are NOT trades
        if action in ("buy", "sell"):
            summary["total_trades"] += 1
            if action == "buy":
                summary["buy_count"] += 1
            elif action == "sell":
                summary["sell_count"] += 1
        elif action == "hold":
            summary["hold_count"] += 1

        sym = summary["symbols"].setdefault(
            symbol,
            {
                "last_action": None,
                "last_price": None,
                "last_amount": None,
                "last_reason": None,
                "last_timestamp": None,
                "pnl": 0.0,
            },
        )
        sym["last_action"] = action or sym["last_action"]
        sym["last_price"] = t.get("price", sym["last_price"])
        sym["last_amount"] = t.get("amount", sym["last_amount"])
        sym["last_reason"] = t.get("reason", sym["last_reason"])
        sym["last_timestamp"] = t.get("timestamp", sym["last_timestamp"])
        sym["pnl"] = pnl_map.get(symbol, 0.0)

    return summary


def load_sentiment() -> Dict[str, Dict[str, Any]]:
    sentiment_file = LOGS_DIR / "sentiment.json"
    data = _safe_load_json(sentiment_file, {})
    if not isinstance(data, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for symbol, v in data.items():
        if not isinstance(v, dict):
            continue
        out[symbol] = {
            "signal": (v.get("signal") or "").upper() or "HOLD",
            "reason": v.get("reason"),
            "updated_at": v.get("updated_at") or v.get("timestamp"),
        }
    return out


# ---------- Routes ----------
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    labels, pnl_data = load_pnl_data()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "labels": labels, "pnl_data": pnl_data},
    )


@router.get("/partial")
async def partial():
    trades = _load_trades()
    summary = build_summary(trades)
    labels, pnl_data = load_pnl_data()
    sentiment = load_sentiment()

    # Fallback sentiment entries for known symbols
    for sym in summary["symbols"].keys():
        if sym not in sentiment:
            sentiment[sym] = {
                "signal": "HOLD",
                "reason": "No headlines yet",
                "updated_at": None,
            }

    # Only last 20 real trades (buy/sell)
    real_trades = [
        t for t in trades if (t.get("action") or "").lower() in ("buy", "sell")
    ][-20:]

    return {
        "summary": summary,
        "labels": labels,
        "pnl_data": pnl_data,
        "sentiment": sentiment,
        "trades": real_trades,
    }


@router.get("/status")
async def status():
    status_data = _load_status()
    return JSONResponse(
        {
            "last_status": {
                "time": status_data.get("time"),
                "message": status_data.get("message"),
            },
            "next_run": status_data.get("next_run"),
        }
    )


"""
Add these routes to src/app/dashboard.py (FastAPI version)

These API endpoints expose strategy signal data for analysis.
"""

# Add this import at the top of dashboard.py (after other imports)
from app.strategy_signal_logger import StrategySignalLogger
from datetime import datetime, timezone

# Initialize the logger (add after router creation)
# signal_logger already initialized at top


# ============================================================================
# NEW API ENDPOINTS - Add these to dashboard.py
# ============================================================================


# Replace BOTH @router.get("/api/balance") functions in dashboard.py with this single one:

# Replace both @router.get("/api/balance") functions in dashboard.py with this:

@router.get("/api/balance")
async def get_balance():
    """
    Get balance for paper trading mode with real Kraken data
    
    Shows:
    - Real Kraken account balance (what you COULD deploy with)
    - Paper trading balance (simulated starting capital)
    - P&L from paper trades
    """
    
    balance_data = {
        "paper_trading": {
            "initial": 100000.0,
            "current": 100000.0,
            "pnl": 0.0,
            "active": True
        },
        "kraken_live": {
            "total_usd": 0.0,
            "balances": {},
            "connected": False
        },
        "mode": "paper",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Calculate paper trading P&L from trades
    try:
        labels, pnl_data = load_pnl_data()
        total_pnl = sum(pnl_data) if pnl_data else 0.0
        
        balance_data["paper_trading"]["pnl"] = round(total_pnl, 2)
        balance_data["paper_trading"]["current"] = round(100000.0 + total_pnl, 2)
        
        logging.info(f"[Balance] Paper trading: ${balance_data['paper_trading']['current']:.2f} (P&L: ${total_pnl:+.2f})")
    except Exception as e:
        logging.error(f"[Balance] Error calculating paper P&L: {e}")
    
    # Fetch REAL Kraken balance (for reference/when going live)
    try:
        from app.client.kraken import KrakenClient
        
        client = KrakenClient()
        kraken_balances = await client.get_balance()
        
        if kraken_balances:
            balance_data["kraken_live"]["connected"] = True
            balance_data["kraken_live"]["balances"] = kraken_balances
            
            # Calculate total USD value from USD-equivalent currencies
            total_usd = 0.0
            for currency in ["ZUSD", "USD", "USDT", "USDC"]:
                if currency in kraken_balances:
                    amount = float(kraken_balances[currency])
                    total_usd += amount
            
            balance_data["kraken_live"]["total_usd"] = round(total_usd, 2)
            
            logging.info(f"[Balance] Real Kraken balance: ${total_usd:.2f} (available for live trading)")
        else:
            logging.warning("[Balance] Kraken returned no balances")
            
    except Exception as e:
        logging.warning(f"[Balance] Could not fetch Kraken balance: {e}")
        balance_data["kraken_live"]["error"] = str(e)
    
    # Return format optimized for dashboard display
    return {
        "total": balance_data["paper_trading"]["current"],
        "available": balance_data["paper_trading"]["current"],
        "pnl": balance_data["paper_trading"]["pnl"],
        "currency": "USD",
        "mode": "paper",
        
        # Additional context
        "paper_initial": balance_data["paper_trading"]["initial"],
        "kraken_balance": balance_data["kraken_live"]["total_usd"],
        "kraken_connected": balance_data["kraken_live"]["connected"],
        
        # For detailed view
        "details": balance_data
    }

@router.get("/api/strategy/current")
async def get_current_signals():
    """
    Get the most recent signal for each symbol.

    Returns:
        {
            "signals": [
                {
                    "symbol": "BTC/USD",
                    "timestamp": "2025-10-10T19:13:25Z",
                    "price": 50000,
                    "final_signal": "BUY",
                    "final_confidence": 0.75,
                    "strategies": { ... }
                },
                ...
            ],
            "count": 3
        }
    """
    try:
        recent_signals = signal_logger.get_recent_signals(limit=100)

        # Get the most recent signal for each symbol
        symbol_signals = {}
        for signal in recent_signals:
            symbol = signal["symbol"]
            if symbol not in symbol_signals:
                symbol_signals[symbol] = signal

        signals_list = list(symbol_signals.values())

        return JSONResponse(
            {"signals": signals_list, "count": len(signals_list), "status": "success"}
        )
    except Exception as e:
        logging.error(f"[API] Error in get_current_signals: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.get("/api/strategy/history")
async def get_signal_history(request: Request):
    """
    Get signal history with optional filtering.

    Query params:
        - symbol: Filter by symbol (optional)
        - limit: Max records to return (default 100, max 1000)

    Returns:
        {
            "signals": [...],
            "count": 50,
            "filtered_by": "BTC/USD" or null
        }
    """
    try:
        symbol = request.query_params.get("symbol")
        limit_str = request.query_params.get("limit", "100")

        try:
            limit = min(int(limit_str), 1000)  # Cap at 1000
        except ValueError:
            return JSONResponse(
                {"error": "Invalid limit parameter", "status": "error"}, status_code=400
            )

        signals = signal_logger.get_recent_signals(limit=limit, symbol=symbol)

        return JSONResponse(
            {
                "signals": signals,
                "count": len(signals),
                "filtered_by": symbol,
                "status": "success",
            }
        )
    except Exception as e:
        logging.error(f"[API] Error in get_signal_history: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.get("/api/strategy/performance")
async def get_strategy_performance(request: Request):
    """
    Get performance metrics for all strategies.

    Query params:
        - lookback_days: How many days to analyze (default 7, max 90)

    Returns:
        {
            "strategies": {
                "technical": {
                    "total_signals": 45,
                    "signal_distribution": {"BUY": 20, "SELL": 15, "HOLD": 10},
                    "avg_confidence": 0.72,
                    "agreement_rate": 0.67,
                    "action_rate": 0.78
                },
                ...
            },
            "lookback_days": 7
        }
    """
    try:
        lookback_str = request.query_params.get("lookback_days", "7")

        try:
            lookback_days = min(int(lookback_str), 90)
        except ValueError:
            return JSONResponse(
                {"error": "Invalid lookback_days parameter", "status": "error"},
                status_code=400,
            )

        performance = signal_logger.get_all_strategies_performance(lookback_days)

        return JSONResponse(
            {
                "strategies": performance,
                "lookback_days": lookback_days,
                "status": "success",
            }
        )
    except Exception as e:
        logging.error(f"[API] Error in get_strategy_performance: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.get("/api/strategy/performance/{strategy_name}")
async def get_single_strategy_performance(strategy_name: str, request: Request):
    """
    Get detailed performance metrics for a specific strategy.

    Query params:
        - lookback_days: How many days to analyze (default 7)

    Returns:
        {
            "strategy_name": "technical",
            "total_signals": 45,
            "signal_distribution": {"BUY": 20, "SELL": 15, "HOLD": 10},
            "avg_confidence": 0.72,
            "agreement_rate": 0.67,
            "action_signals": 35,
            "action_rate": 0.78
        }
    """
    try:
        lookback_str = request.query_params.get("lookback_days", "7")

        try:
            lookback_days = int(lookback_str)
        except ValueError:
            return JSONResponse(
                {"error": "Invalid lookback_days parameter", "status": "error"},
                status_code=400,
            )

        performance = signal_logger.get_strategy_performance(
            strategy_name, lookback_days
        )

        if performance["total_signals"] == 0:
            return JSONResponse(
                {
                    "error": f"No data found for strategy '{strategy_name}'",
                    "status": "not_found",
                },
                status_code=404,
            )

        return JSONResponse({**performance, "status": "success"})
    except Exception as e:
        logging.error(f"[API] Error in get_single_strategy_performance: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.get("/api/strategy/correlation")
async def get_strategy_correlation():
    """
    Get correlation matrix showing agreement between strategies.

    Returns:
        {
            "correlations": {
                "technical": {
                    "technical": 1.0,
                    "volume": 0.65,
                    "sentiment": 0.72
                },
                ...
            },
            "description": "1.0 = always agree, 0.0 = never agree"
        }
    """
    try:
        correlations = signal_logger.get_signal_correlation()

        if not correlations:
            return JSONResponse(
                {
                    "correlations": {},
                    "message": "No signal data available",
                    "status": "success",
                }
            )

        return JSONResponse(
            {
                "correlations": correlations,
                "description": "1.0 = always agree, 0.0 = never agree",
                "status": "success",
            }
        )
    except Exception as e:
        logging.error(f"[API] Error in get_strategy_correlation: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.get("/api/strategy/summary")
async def get_strategy_summary():
    """
    Get a high-level summary of all strategy data.

    Returns:
        {
            "total_decisions": 1523,
            "total_strategies": 3,
            "date_range": {
                "oldest": "2025-10-01T10:00:00Z",
                "newest": "2025-10-10T19:13:25Z"
            },
            "symbols_tracked": ["BTC/USD", "ETH/USD"],
            "aggregation_methods": {
                "weighted_vote": 1420,
                "highest_confidence": 75
            }
        }
    """
    try:
        all_signals = signal_logger.get_recent_signals(limit=10000)

        if not all_signals:
            return JSONResponse(
                {
                    "total_decisions": 0,
                    "message": "No signal data available",
                    "status": "success",
                }
            )

        # Extract summary stats
        symbols = set(s["symbol"] for s in all_signals)
        aggregation_counts = {}

        for signal in all_signals:
            method = signal.get("aggregation_method", "unknown")
            aggregation_counts[method] = aggregation_counts.get(method, 0) + 1

        # Get date range
        timestamps = [s["timestamp"] for s in all_signals]

        # Get unique strategies
        all_strategy_names = set()
        for signal in all_signals:
            all_strategy_names.update(signal.get("strategies", {}).keys())

        return JSONResponse(
            {
                "total_decisions": len(all_signals),
                "total_strategies": len(all_strategy_names),
                "strategy_names": sorted(list(all_strategy_names)),
                "date_range": {"oldest": min(timestamps), "newest": max(timestamps)},
                "symbols_tracked": sorted(list(symbols)),
                "aggregation_methods": aggregation_counts,
                "status": "success",
            }
        )
    except Exception as e:
        logging.error(f"[API] Error in get_strategy_summary: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.get("/api/strategy/signals/latest")
async def get_latest_signal():
    """
    Get the absolute latest signal across all symbols.

    Returns:
        {
            "signal": { ... },
            "age_seconds": 42
        }
    """
    try:
        signals = signal_logger.get_recent_signals(limit=1)

        if not signals:
            return JSONResponse(
                {"error": "No signals available", "status": "not_found"},
                status_code=404,
            )

        latest = signals[0]

        # Calculate age
        signal_time = datetime.fromisoformat(latest["timestamp"])
        now = datetime.now(timezone.utc)
        age_seconds = (now - signal_time).total_seconds()

        return JSONResponse(
            {"signal": latest, "age_seconds": age_seconds, "status": "success"}
        )
    except Exception as e:
        logging.error(f"[API] Error in get_latest_signal: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


# Add these imports at the top of dashboard.py
from typing import Optional
import time
import asyncio
from datetime import datetime, timedelta

# You'll need to add these to track RSS feeds
# Add after signal_logger initialization
RSS_FEEDS_FILE = LOGS_DIR / "rss_feeds.json"

# ============================================================================
# HEALTH MONITORING API
# ============================================================================


@router.get("/api/health")
async def get_system_health():
    """
    Get health status of all system dependencies.

    Returns:
        {
            "openai": {
                "status": "operational" | "degraded" | "error",
                "latency": 245,
                "lastCheck": "2025-01-15T10:30:00Z",
                "errors24h": 0
            },
            "exchange": { ... },
            "rssFeeds": { ... },
            "database": { ... }
        }
    """
    try:
        health_data = {}

        # Check OpenAI
        openai_start = time.time()
        openai_status = await check_openai_health()
        openai_latency = int((time.time() - openai_start) * 1000)

        health_data["openai"] = {
            "status": openai_status["status"],
            "latency": openai_latency,
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errors24h": openai_status.get("errors", 0),
        }

        # Check Exchange (placeholder - implement based on your exchange)
        exchange_start = time.time()
        exchange_status = await check_exchange_health()
        exchange_latency = int((time.time() - exchange_start) * 1000)

        health_data["exchange"] = {
            "status": exchange_status["status"],
            "latency": exchange_latency,
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errors24h": exchange_status.get("errors", 0),
        }

        # Check RSS Feeds
        rss_start = time.time()
        rss_status = await check_rss_feeds_health()
        rss_latency = int((time.time() - rss_start) * 1000)

        health_data["rssFeeds"] = {
            "status": rss_status["status"],
            "latency": rss_latency,
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errors24h": rss_status.get("errors", 0),
        }

        # Check Database/File System
        db_start = time.time()
        db_status = check_database_health()
        db_latency = int((time.time() - db_start) * 1000)

        health_data["database"] = {
            "status": db_status["status"],
            "latency": db_latency,
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errors24h": db_status.get("errors", 0),
        }

        return JSONResponse(health_data)

    except Exception as e:
        logging.error(f"[API] Error in get_system_health: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


async def check_openai_health() -> Dict[str, Any]:
    """Check OpenAI API health."""
    try:
        # TODO: Implement actual OpenAI health check
        # For now, check if we have recent errors in logs
        error_count = 0

        # Check sentiment.json for recent successful updates
        sentiment = load_sentiment()
        if sentiment:
            # If we have recent sentiment data, OpenAI is likely working
            return {"status": "operational", "errors": 0}

        return {"status": "degraded", "errors": error_count}
    except Exception as e:
        logging.error(f"[Health] OpenAI check failed: {e}")
        return {"status": "error", "errors": 1}


# Find the check_exchange_health() function in dashboard.py
# (around line 550-570) and replace it with this simpler version:


async def check_exchange_health() -> Dict[str, Any]:
    """Check exchange API health."""
    try:
        # Check if we have recent trades
        trades = _load_trades()
        if not trades:
            return {"status": "degraded", "errors": 0}

        # Check if last trade is recent (within 24h)
        last_trade = trades[-1]
        last_timestamp = last_trade.get("timestamp")

        if last_timestamp:
            try:
                # Parse timestamp - handle both formats
                if last_timestamp.endswith("Z"):
                    last_timestamp = last_timestamp.replace("Z", "+00:00")

                last_time = datetime.fromisoformat(last_timestamp)

                # Make timezone-aware if needed
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)

                now = datetime.now(timezone.utc)
                time_diff = now - last_time

                if time_diff < timedelta(hours=24):
                    return {"status": "operational", "errors": 0}
                else:
                    return {"status": "degraded", "errors": 0}

            except Exception as e:
                logging.error(f"[Health] Timestamp parse error: {e}")
                return {"status": "degraded", "errors": 0}

        return {"status": "operational", "errors": 0}

    except Exception as e:
        logging.error(f"[Health] Exchange check failed: {e}")
        return {"status": "error", "errors": 1}


async def check_rss_feeds_health() -> Dict[str, Any]:
    """Check RSS feeds health."""
    try:
        feeds = _load_rss_feeds()
        if not feeds:
            return {"status": "degraded", "errors": 0}

        error_count = sum(1 for f in feeds if f.get("status") == "error")
        total_feeds = len(feeds)

        if error_count == 0:
            return {"status": "operational", "errors": 0}
        elif error_count < total_feeds:
            return {"status": "degraded", "errors": error_count}
        else:
            return {"status": "error", "errors": error_count}

    except Exception as e:
        logging.error(f"[Health] RSS feeds check failed: {e}")
        return {"status": "error", "errors": 1}


def check_database_health() -> Dict[str, Any]:
    """Check database/file system health."""
    try:
        # Check if we can read/write to logs directory
        test_file = LOGS_DIR / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()

        # Check if key files exist and are readable
        required_files = [LOGS_DIR / "trades.json", LOGS_DIR / "bot_status.json"]

        for file in required_files:
            if file.exists():
                file.read_text()

        return {"status": "operational", "errors": 0}
    except Exception as e:
        logging.error(f"[Health] Database check failed: {e}")
        return {"status": "error", "errors": 1}


# ============================================================================
# RSS FEED MANAGEMENT API
# ============================================================================


def _load_rss_feeds() -> List[Dict[str, Any]]:
    """Load RSS feeds from JSON file."""
    feeds = _safe_load_json(RSS_FEEDS_FILE, [])
    if not isinstance(feeds, list):
        return []
    return feeds


def _save_rss_feeds(feeds: List[Dict[str, Any]]) -> bool:
    """Save RSS feeds to JSON file."""
    try:
        with RSS_FEEDS_FILE.open("w") as f:
            json.dump(feeds, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"[Feeds] Failed to save feeds: {e}")
        return False


@router.get("/api/feeds")
async def get_rss_feeds():
    """
    Get all configured RSS feeds.

    Returns:
        [
            {
                "id": 1,
                "name": "CoinDesk",
                "url": "https://coindesk.com/feed",
                "status": "active" | "error",
                "last_fetch": "2025-01-15T10:25:00Z",
                "headlines_count": 47,
                "relevant_count": 12,
                "error": "Connection timeout" (optional)
            },
            ...
        ]
    """
    try:
        feeds = _load_rss_feeds()
        return JSONResponse({"feeds": feeds, "total": len(feeds)})
    except Exception as e:
        logging.error(f"[API] Error in get_rss_feeds: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.post("/api/feeds")
async def add_rss_feed(request: Request):
    """
    Add a new RSS feed.

    Body:
        {
            "url": "https://example.com/feed",
            "name": "Example Feed" (optional)
        }

    Returns:
        {
            "id": 4,
            "url": "https://example.com/feed",
            "name": "Example Feed",
            "status": "active",
            "message": "Feed added successfully"
        }
    """
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        name = body.get("name", "").strip()

        if not url:
            return JSONResponse(
                {"error": "URL is required", "status": "error"}, status_code=400
            )

        # Validate URL format
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return JSONResponse(
                {"error": "Invalid URL format", "status": "error"}, status_code=400
            )

        # Load existing feeds
        feeds = _load_rss_feeds()

        # Check for duplicates
        if any(f.get("url") == url for f in feeds):
            return JSONResponse(
                {"error": "Feed URL already exists", "status": "error"}, status_code=400
            )

        # Generate new ID
        new_id = max([f.get("id", 0) for f in feeds], default=0) + 1

        # Extract name from URL if not provided
        if not name:
            name = parsed.netloc.replace("www.", "")

        # Create new feed
        new_feed = {
            "id": new_id,
            "name": name,
            "url": url,
            "status": "active",
            "last_fetch": None,
            "headlines_count": 0,
            "relevant_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        feeds.append(new_feed)

        # Save feeds
        if not _save_rss_feeds(feeds):
            return JSONResponse(
                {"error": "Failed to save feed", "status": "error"}, status_code=500
            )

        logging.info(f"[Feeds] Added new feed: {name} ({url})")

        return JSONResponse(
            {**new_feed, "message": "Feed added successfully", "status": "success"}
        )

    except json.JSONDecodeError:
        return JSONResponse(
            {"error": "Invalid JSON body", "status": "error"}, status_code=400
        )
    except Exception as e:
        logging.error(f"[API] Error in add_rss_feed: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.delete("/api/feeds/{feed_id}")
async def delete_rss_feed(feed_id: int):
    """
    Delete an RSS feed by ID.

    Returns:
        {
            "message": "Feed deleted successfully",
            "id": 3
        }
    """
    try:
        feeds = _load_rss_feeds()

        # Find feed
        feed_to_delete = None
        for i, feed in enumerate(feeds):
            if feed.get("id") == feed_id:
                feed_to_delete = feeds.pop(i)
                break

        if not feed_to_delete:
            return JSONResponse(
                {"error": f"Feed with ID {feed_id} not found", "status": "error"},
                status_code=404,
            )

        # Save updated feeds
        if not _save_rss_feeds(feeds):
            return JSONResponse(
                {"error": "Failed to save feeds", "status": "error"}, status_code=500
            )

        logging.info(
            f"[Feeds] Deleted feed: {feed_to_delete.get('name')} (ID: {feed_id})"
        )

        return JSONResponse(
            {"message": "Feed deleted successfully", "id": feed_id, "status": "success"}
        )

    except Exception as e:
        logging.error(f"[API] Error in delete_rss_feed: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.put("/api/feeds/{feed_id}")
async def update_rss_feed(feed_id: int, request: Request):
    """
    Update an RSS feed's status or metadata.

    Body:
        {
            "name": "New Name" (optional),
            "status": "active" | "error" (optional),
            "last_fetch": "2025-01-15T10:25:00Z" (optional),
            "headlines_count": 50 (optional),
            "relevant_count": 15 (optional),
            "error": "Error message" (optional)
        }

    Returns:
        {
            "message": "Feed updated successfully",
            "feed": { ... }
        }
    """
    try:
        body = await request.json()
        feeds = _load_rss_feeds()

        # Find feed
        feed_to_update = None
        for feed in feeds:
            if feed.get("id") == feed_id:
                feed_to_update = feed
                break

        if not feed_to_update:
            return JSONResponse(
                {"error": f"Feed with ID {feed_id} not found", "status": "error"},
                status_code=404,
            )

        # Update fields
        updatable_fields = [
            "name",
            "status",
            "last_fetch",
            "headlines_count",
            "relevant_count",
            "error",
        ]

        for field in updatable_fields:
            if field in body:
                feed_to_update[field] = body[field]

        feed_to_update["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Save updated feeds
        if not _save_rss_feeds(feeds):
            return JSONResponse(
                {"error": "Failed to save feeds", "status": "error"}, status_code=500
            )

        logging.info(f"[Feeds] Updated feed ID {feed_id}")

        return JSONResponse(
            {
                "message": "Feed updated successfully",
                "feed": feed_to_update,
                "status": "success",
            }
        )

    except json.JSONDecodeError:
        return JSONResponse(
            {"error": "Invalid JSON body", "status": "error"}, status_code=400
        )
    except Exception as e:
        logging.error(f"[API] Error in update_rss_feed: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)
