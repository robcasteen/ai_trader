from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from collections import defaultdict
from typing import Dict, Any, List, Tuple
import json
import logging
from app.strategy_signal_logger import StrategySignalLogger
from datetime import datetime, timezone, timedelta
import time

router = APIRouter()

# === Paths ===
PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PROJECT_ROOT.parent / "templates"
LOGS_DIR = PROJECT_ROOT / "logs"

# Initialize
signal_logger = StrategySignalLogger(data_dir=str(LOGS_DIR))
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
RSS_FEEDS_FILE = LOGS_DIR / "rss_feeds.json"


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
    status_file = LOGS_DIR / "bot_status.json"
    data = _safe_load_json(status_file, {"time": None, "message": "Unknown"})
    if not isinstance(data, dict):
        data = {"time": None, "message": "Unknown"}
    if "next_run" not in data:
        data["next_run"] = None
    return data


def _load_rss_feeds() -> List[Dict[str, Any]]:
    feeds = _safe_load_json(RSS_FEEDS_FILE, [])
    if not isinstance(feeds, list):
        return []
    return feeds


def _save_rss_feeds(feeds: List[Dict[str, Any]]) -> bool:
    try:
        with RSS_FEEDS_FILE.open("w") as f:
            json.dump(feeds, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"[Feeds] Failed to save feeds: {e}")
        return False


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
        "hold_count": 0,
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

    for sym in summary["symbols"].keys():
        if sym not in sentiment:
            sentiment[sym] = {
                "signal": "HOLD",
                "reason": "No headlines yet",
                "updated_at": None,
            }

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


@router.get("/api/balance")
async def get_balance():
    balance_data = {
        "paper_trading": {
            "initial": 100000.0,
            "current": 100000.0,
            "pnl": 0.0,
            "active": True,
        },
        "kraken_live": {"total_usd": 0.0, "balances": {}, "connected": False},
        "mode": "paper",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        labels, pnl_data = load_pnl_data()
        total_pnl = sum(pnl_data) if pnl_data else 0.0

        balance_data["paper_trading"]["pnl"] = round(total_pnl, 2)
        balance_data["paper_trading"]["current"] = round(100000.0 + total_pnl, 2)

        logging.info(
            f"[Balance] Paper trading: ${balance_data['paper_trading']['current']:.2f} (P&L: ${total_pnl:+.2f})"
        )
    except Exception as e:
        logging.error(f"[Balance] Error calculating paper P&L: {e}")

    try:
        from app.client.kraken import KrakenClient

        client = KrakenClient()
        kraken_balances = client.get_balance()

        if kraken_balances:
            balance_data["kraken_live"]["connected"] = True
            balance_data["kraken_live"]["balances"] = kraken_balances

            total_usd = 0.0
            for currency in ["ZUSD", "USD", "USDT", "USDC"]:
                if currency in kraken_balances:
                    amount = float(kraken_balances[currency])
                    total_usd += amount

            balance_data["kraken_live"]["total_usd"] = round(total_usd, 2)
            logging.info(
                f"[Balance] Real Kraken balance: ${total_usd:.2f} (available for live trading)"
            )
        else:
            logging.warning("[Balance] Kraken returned no balances")

    except Exception as e:
        logging.warning(f"[Balance] Could not fetch Kraken balance: {e}")
        balance_data["kraken_live"]["error"] = str(e)

    return {
        "total": balance_data["paper_trading"]["current"],
        "available": balance_data["paper_trading"]["current"],
        "pnl": balance_data["paper_trading"]["pnl"],
        "currency": "USD",
        "mode": "paper",
        "paper_initial": balance_data["paper_trading"]["initial"],
        "kraken_balance": balance_data["kraken_live"]["total_usd"],
        "kraken_connected": balance_data["kraken_live"]["connected"],
        "details": balance_data,
    }


@router.get("/api/holdings")
async def get_holdings():
    """Get current holdings/positions calculated from trade history."""
    trades_file = LOGS_DIR / "trades.json"
    TRADING_FEE = 0.0026  # 0.26% trading fee

    try:
        holdings = {}

        if trades_file.exists():
            with open(trades_file, "r") as f:
                trades = json.load(f)

            for trade in trades:
                symbol = trade.get("symbol", "")
                action = trade.get("action", "").lower()
                amount = trade.get("amount", 0)
                price = trade.get("price", 0)

                if action == "hold":
                    continue

                if action == "buy":
                    if symbol not in holdings:
                        holdings[symbol] = {
                            "amount": 0.0,
                            "total_cost": 0.0,
                            "trades": [],
                        }

                    # Add trading fee to cost basis
                    cost_with_fee = (amount * price) * (1 + TRADING_FEE)
                    holdings[symbol]["amount"] += amount
                    holdings[symbol]["total_cost"] += cost_with_fee
                    holdings[symbol]["trades"].append(trade)

                elif action == "sell":
                    if symbol in holdings and holdings[symbol]["amount"] > 0:
                        # Reduce position proportionally
                        proportion_sold = amount / holdings[symbol]["amount"]
                        cost_reduction = (
                            holdings[symbol]["total_cost"] * proportion_sold
                        )

                        holdings[symbol]["amount"] -= amount
                        holdings[symbol]["total_cost"] -= cost_reduction
                        holdings[symbol]["trades"].append(trade)

                        if holdings[symbol]["amount"] <= 0.0001:
                            del holdings[symbol]

        # Get current prices
        from app.client.kraken import KrakenClient

        kraken_client = KrakenClient()

        formatted_holdings = {}
        for symbol, data in holdings.items():
            current_price = kraken_client.get_price(symbol)
            amount = data["amount"]
            avg_price = data["total_cost"] / amount if amount > 0 else 0
            market_value = amount * current_price
            cost_basis = data["total_cost"]
            unrealized_pnl = market_value - cost_basis

            formatted_holdings[symbol] = {
                "amount": round(amount, 8),
                "avg_price": round(avg_price, 2),
                "current_price": round(current_price, 2),
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_percent": round(
                    (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0, 2
                ),
                "num_trades": len(data["trades"]),
            }

        total_value = sum(h["market_value"] for h in formatted_holdings.values())
        total_cost = sum(h["cost_basis"] for h in formatted_holdings.values())
        total_pnl = total_value - total_cost

        return {
            "holdings": formatted_holdings,
            "summary": {
                "total_positions": len(formatted_holdings),
                "total_market_value": round(total_value, 2),
                "total_cost_basis": round(total_cost, 2),
                "total_unrealized_pnl": round(total_pnl, 2),
                "total_unrealized_pnl_percent": round(
                    (total_pnl / total_cost * 100) if total_cost > 0 else 0, 2
                ),
            },
        }

    except Exception as e:
        logging.error(f"[Holdings] Error calculating from trades: {e}")
        return {
            "holdings": {},
            "summary": {
                "total_positions": 0,
                "total_market_value": 0.0,
                "total_cost_basis": 0.0,
                "total_unrealized_pnl": 0.0,
                "total_unrealized_pnl_percent": 0.0,
            },
        }


# Strategy API endpoints
@router.get("/api/strategy/current")
async def get_current_signals():
    try:
        recent_signals = signal_logger.get_recent_signals(limit=100)
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
    try:
        symbol = request.query_params.get("symbol")
        limit_str = request.query_params.get("limit", "100")

        try:
            limit = min(int(limit_str), 1000)
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

        symbols = set(s["symbol"] for s in all_signals)
        aggregation_counts = {}

        for signal in all_signals:
            method = signal.get("aggregation_method", "unknown")
            aggregation_counts[method] = aggregation_counts.get(method, 0) + 1

        timestamps = [s["timestamp"] for s in all_signals]
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
    try:
        signals = signal_logger.get_recent_signals(limit=1)

        if not signals:
            return JSONResponse(
                {"error": "No signals available", "status": "not_found"},
                status_code=404,
            )

        latest = signals[0]
        signal_time = datetime.fromisoformat(latest["timestamp"])
        now = datetime.now(timezone.utc)
        age_seconds = (now - signal_time).total_seconds()

        return JSONResponse(
            {"signal": latest, "age_seconds": age_seconds, "status": "success"}
        )
    except Exception as e:
        logging.error(f"[API] Error in get_latest_signal: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


# Health monitoring
@router.get("/api/health")
async def get_system_health():
    try:
        health_data = {}

        openai_start = time.time()
        openai_status = await check_openai_health()
        openai_latency = int((time.time() - openai_start) * 1000)

        health_data["openai"] = {
            "status": openai_status["status"],
            "latency": openai_latency,
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errors24h": openai_status.get("errors", 0),
        }

        exchange_start = time.time()
        exchange_status = await check_exchange_health()
        exchange_latency = int((time.time() - exchange_start) * 1000)

        health_data["exchange"] = {
            "status": exchange_status["status"],
            "latency": exchange_latency,
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errors24h": exchange_status.get("errors", 0),
        }

        rss_start = time.time()
        rss_status = await check_rss_feeds_health()
        rss_latency = int((time.time() - rss_start) * 1000)

        health_data["rssFeeds"] = {
            "status": rss_status["status"],
            "latency": rss_latency,
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errors24h": rss_status.get("errors", 0),
        }

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


@router.get("/api/trades/all")
async def get_all_trades():
    """Get all trades without limit."""
    trades_file = Path("src/app/logs/trades.json")

    try:
        if not trades_file.exists():
            return JSONResponse([])

        with open(trades_file, "r") as f:
            all_trades = json.load(f)

        # Filter out HOLD actions - only return actual trades (BUY/SELL)
        real_trades = [
            t for t in all_trades if (t.get("action") or "").lower() in ("buy", "sell")
        ]

        return JSONResponse(real_trades)
    except Exception as e:
        logging.error(f"[API] Error loading all trades: {e}")
        return JSONResponse([], status_code=500)


async def check_openai_health() -> Dict[str, Any]:
    try:
        error_count = 0
        sentiment = load_sentiment()
        if sentiment:
            return {"status": "operational", "errors": 0}
        return {"status": "degraded", "errors": error_count}
    except Exception as e:
        logging.error(f"[Health] OpenAI check failed: {e}")
        return {"status": "error", "errors": 1}


async def check_exchange_health() -> Dict[str, Any]:
    try:
        trades = _load_trades()
        if not trades:
            return {"status": "degraded", "errors": 0}

        last_trade = trades[-1]
        last_timestamp = last_trade.get("timestamp")

        if last_timestamp:
            try:
                if last_timestamp.endswith("Z"):
                    last_timestamp = last_timestamp.replace("Z", "+00:00")

                last_time = datetime.fromisoformat(last_timestamp)

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
    try:
        test_file = LOGS_DIR / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()

        required_files = [LOGS_DIR / "trades.json", LOGS_DIR / "bot_status.json"]

        for file in required_files:
            if file.exists():
                file.read_text()

        return {"status": "operational", "errors": 0}
    except Exception as e:
        logging.error(f"[Health] Database check failed: {e}")
        return {"status": "error", "errors": 1}


# RSS Feed Management
@router.get("/api/feeds")
async def get_rss_feeds():
    try:
        feeds = _load_rss_feeds()
        # Ensure all feeds have active field (default True)
        for feed in feeds:
            if "active" not in feed:
                feed["active"] = True
        return JSONResponse({"feeds": feeds, "total": len(feeds)})
    except Exception as e:
        logging.error(f"[API] Error in get_rss_feeds: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.post("/api/feeds")
async def add_rss_feed(request: Request):
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        name = body.get("name", "").strip()

        if not url:
            return JSONResponse(
                {"error": "URL is required", "status": "error"}, status_code=400
            )

        from urllib.parse import urlparse

        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return JSONResponse(
                {"error": "Invalid URL format", "status": "error"}, status_code=400
            )

        feeds = _load_rss_feeds()

        if any(f.get("url") == url for f in feeds):
            return JSONResponse(
                {"error": "Feed URL already exists", "status": "error"}, status_code=400
            )

        new_id = max([f.get("id", 0) for f in feeds], default=0) + 1

        if not name:
            name = parsed.netloc.replace("www.", "")

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
    try:
        feeds = _load_rss_feeds()

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


# Configuration Management
@router.get("/api/config")
async def get_config():
    """Get current trading configuration."""
    config_file = Path("src/config/config.json")

    try:
        with open(config_file, "r") as f:
            config = json.load(f)

        # Add defaults for any missing values
        defaults = {
            "strategy": config.get("strategy", "gpt-sentiment"),
            "interval_minutes": config.get("interval_minutes", 5),
            "trading_fee_percent": config.get("trading_fee_percent", 0.26),
            "trading_mode": config.get("trading_mode", "paper"),
            "paper_starting_capital": config.get("paper_starting_capital", 100000),
            "strategies": config.get(
                "strategies",
                {
                    "sentiment": {"enabled": True, "weight": 1.0},
                    "technical": {"enabled": True, "weight": 1.0},
                    "volume": {"enabled": True, "weight": 0.8},
                },
            ),
            "risk_management": config.get(
                "risk_management",
                {
                    "position_size_percent": 3.0,
                    "max_daily_loss_percent": 5.0,
                    "max_open_positions": None,
                },
            ),
            "aggregation": config.get(
                "aggregation", {"method": "weighted_vote", "min_confidence": 0.5}
            ),
        }

        # Merge defaults with existing config
        for key, value in defaults.items():
            if key not in config:
                config[key] = value

        return JSONResponse({"config": config, "status": "success"})

    except Exception as e:
        logging.error(f"[API] Error loading config: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.post("/api/config")
async def update_config(request: Request):
    """Update trading configuration."""
    config_file = Path("src/config/config.json")

    try:
        body = await request.json()
        new_config = body.get("config", {})

        # Validate trading mode
        if "trading_mode" in new_config:
            if new_config["trading_mode"] not in ["paper", "live"]:
                return JSONResponse(
                    {
                        "error": "trading_mode must be 'paper' or 'live'",
                        "status": "error",
                    },
                    status_code=400,
                )

        # Load current config
        with open(config_file, "r") as f:
            config = json.load(f)

        # Deep merge new config
        def deep_merge(base, updates):
            for key, value in updates.items():
                if (
                    isinstance(value, dict)
                    and key in base
                    and isinstance(base[key], dict)
                ):
                    deep_merge(base[key], value)
                else:
                    base[key] = value

        deep_merge(config, new_config)

        # Save
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        logging.info(f"[Config] Updated configuration: {list(new_config.keys())}")

        return JSONResponse(
            {
                "message": "Configuration updated successfully",
                "config": config,
                "status": "success",
            }
        )

    except Exception as e:
        logging.error(f"[API] Error updating config: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.put("/api/feeds/{feed_id}")
async def update_rss_feed(feed_id: int, request: Request):
    try:
        body = await request.json()
        feeds = _load_rss_feeds()

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


@router.put("/api/feeds/{feed_id}/toggle")
async def toggle_rss_feed(feed_id: int):
    """Toggle active/inactive status of an RSS feed."""
    try:
        feeds = _load_rss_feeds()

        # Find feed by ID
        feed = next((f for f in feeds if f["id"] == feed_id), None)

        if feed is None:
            return JSONResponse(
                status_code=404, content={"error": f"Feed ID {feed_id} not found"}
            )

        # Toggle the active field (default to True if not present)
        feed["active"] = not feed.get("active", True)

        # Save
        if _save_rss_feeds(feeds):
            status = "enabled" if feed["active"] else "disabled"
            logging.info(f"[Feeds] Toggled feed ID {feed_id}: {status}")
            return {"success": True, "active": feed["active"], "feed_id": feed_id}

        return JSONResponse(
            status_code=500, content={"error": "Failed to save feed changes"}
        )
    except Exception as e:
        logging.error(f"[Feeds] Error toggling feed {feed_id}: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/feeds/{feed_id}/test")
async def test_rss_feed(feed_id: int):
    """Test an RSS feed by ID."""
    try:
        import feedparser
        
        feeds = _load_rss_feeds()
        feed = next((f for f in feeds if f["id"] == feed_id), None)
        
        if not feed:
            return JSONResponse(
                status_code=404, content={"error": f"Feed ID {feed_id} not found"}
            )
        
        url = feed.get("url")
        if not url:
            return JSONResponse(
                status_code=400, content={"error": "Feed has no URL"}
            )
        
        parsed = feedparser.parse(url)
        
        if parsed.bozo:
            error_msg = str(parsed.bozo_exception) if hasattr(parsed, 'bozo_exception') else "Invalid feed"
            return JSONResponse(status_code=400, content={"error": error_msg, "status": "error"})
        
        entry_count = len(parsed.entries)
        title = parsed.feed.get("title", "Unknown")
        
        return {
            "status": "success",
            "entries": entry_count,
            "title": title,
            "message": f"Feed OK - {entry_count} entries found"
        }
    except Exception as e:
        logging.error(f"[Feeds] Error testing feed {feed_id}: {e}")
        return JSONResponse(status_code=500, content={"error": str(e), "status": "error"})