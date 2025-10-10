from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from collections import defaultdict
from typing import Dict, Any, List, Tuple
import json
import logging

router = APIRouter()

# === Paths ===
PROJECT_ROOT = Path(__file__).resolve().parents[1]   # /src
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
                pos["price"] = total_cost / total_amount if total_amount else pos["price"]
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
                pos["price"] = total_cost / total_amount if total_amount else pos["price"]
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

        sym = summary["symbols"].setdefault(symbol, {
            "last_action": None,
            "last_price": None,
            "last_amount": None,
            "last_reason": None,
            "last_timestamp": None,
            "pnl": 0.0,
        })
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
    real_trades = [t for t in trades if (t.get("action") or "").lower() in ("buy", "sell")][-20:]

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
    return JSONResponse({
        "last_status": {
            "time": status_data.get("time"),
            "message": status_data.get("message"),
        },
        "next_run": status_data.get("next_run"),
    })


