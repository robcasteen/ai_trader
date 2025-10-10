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
# Initialize strategy signal logger
signal_logger = StrategySignalLogger()

# === Paths ===
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # /src
TEMPLATES_DIR = PROJECT_ROOT / "templates"
LOGS_DIR = PROJECT_ROOT / "logs"

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
signal_logger = StrategySignalLogger()


# ============================================================================
# NEW API ENDPOINTS - Add these to dashboard.py
# ============================================================================


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
