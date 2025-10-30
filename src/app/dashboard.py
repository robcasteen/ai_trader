from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from collections import defaultdict
from typing import Dict, Any, List, Tuple
from decimal import Decimal
import json
import logging
import asyncio
from app.strategy_signal_logger import StrategySignalLogger
from datetime import datetime, timezone, timedelta
from app.error_tracker import error_tracker
from app.events import event_bus, EventType
import time

# Database imports
from app.database.connection import get_db
from app.database.repositories import SignalRepository, TradeRepository, HoldingRepository, RSSFeedRepository, BotConfigRepository
from sqlalchemy import func, desc

router = APIRouter()

# === Paths ===
PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PROJECT_ROOT.parent / "templates"
LOGS_DIR = PROJECT_ROOT / "logs"

# Initialize
signal_logger = StrategySignalLogger(data_dir=str(LOGS_DIR))
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# REMOVED: RSS_FEEDS_FILE - feeds now in database


# ---------- Utilities ----------
# REMOVED: _safe_load_json - all data now comes from database


def _load_trades() -> List[Dict[str, Any]]:
    """Load trades from database."""
    try:
        with get_db() as db:
            repo = TradeRepository(db)
            trade_models = repo.get_all(test_mode=False)

            # Convert to dict format for compatibility
            trades = []
            for t in trade_models:
                trades.append({
                    "id": t.id,
                    "timestamp": t.timestamp.isoformat() + 'Z' if t.timestamp else None,
                    "action": t.action,
                    "symbol": t.symbol,
                    "price": float(t.price) if t.price else 0,
                    "amount": float(t.amount) if t.amount else 0,
                    "gross_value": float(t.gross_value) if t.gross_value else 0,
                    "fee": float(t.fee) if t.fee else 0,
                    "net_value": float(t.net_value) if t.net_value else 0,
                    "reason": t.reason,
                    "strategies_used": t.strategies_used,
                    "signal_id": t.signal_id,
                })

            logging.info(f"[Dashboard] Loaded {len(trades)} trades from database")
            return trades
    except Exception as e:
        logging.error(f"[Dashboard] Failed to load trades from database: {e}")
        return []


def _load_status() -> Dict[str, Any]:
    """Load bot status from database."""
    from datetime import timezone

    try:
        with get_db() as db:
            from app.database.repositories import BotConfigRepository, SignalRepository
            config_repo = BotConfigRepository(db)
            signal_repo = SignalRepository(db)

            status = config_repo.get_current()

            # Get next run time from scheduler (already in local time)
            from app.main import scheduler
            next_run_time = None
            try:
                job = scheduler.get_job("trade_cycle")
                if job and job.next_run_time:
                    next_run_time = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

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

            if status:
                return {
                    "time": last_run_time,
                    "message": f"Mode: {status.mode}, Min Confidence: {status.min_confidence}",
                    "next_run": next_run_time
                }
    except Exception as e:
        logging.error(f"[Dashboard] Failed to load status from database: {e}")

    return {"time": None, "message": "Unknown", "next_run": None}


def _load_rss_feeds() -> List[Dict[str, Any]]:
    """Load RSS feeds from database with headline counts."""
    try:
        with get_db() as db:
            from app.database.models import SeenNews
            repo = RSSFeedRepository(db)
            feed_models = repo.get_all()

            # Get relevant headline counts per feed
            # "relevant" means headlines that mentioned crypto symbols (saved to seen_news)
            relevant_counts = db.query(
                SeenNews.feed_id,
                func.count(SeenNews.id).label('relevant')
            ).group_by(SeenNews.feed_id).all()

            # Convert to dict for lookup
            relevant_by_feed = {row.feed_id: row.relevant for row in relevant_counts}

            # Convert to dict format for compatibility
            feeds = []
            for f in feed_models:
                # total_items_fetched = all headlines fetched from feed
                # relevant = headlines with crypto symbols (saved to seen_news)
                total = f.total_items_fetched or 0
                relevant = relevant_by_feed.get(f.id, 0)

                feeds.append({
                    "id": f.id,
                    "url": f.url,
                    "name": f.name,
                    "enabled": f.enabled,
                    "active": f.enabled,  # Backwards compatibility
                    "keywords": f.keywords or [],
                    "last_fetch": f.last_fetch.isoformat() + 'Z' if f.last_fetch else None,
                    "last_error": f.last_error,
                    "created_at": f.created_at.isoformat() + 'Z' if f.created_at else None,
                    "headlines_count": int(total),
                    "relevant_count": int(relevant),
                })

            logging.info(f"[Dashboard] Loaded {len(feeds)} RSS feeds from database")
            return feeds
    except Exception as e:
        logging.error(f"[Dashboard] Failed to load feeds from database: {e}")
        return []


# REMOVED: _save_rss_feeds - feeds are now saved to database only


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
    """Load sentiment data from recent signals in database."""
    try:
        with get_db() as db:
            signal_repo = SignalRepository(db)
            recent_signals = signal_repo.get_recent(hours=24, test_mode=False, limit=100)

            # Get most recent signal per symbol
            sentiment = {}
            for sig in recent_signals:
                symbol = sig.symbol
                if symbol not in sentiment:
                    # Extract sentiment strategy data if available
                    strategies = sig.strategies or {}
                    sentiment_data = strategies.get("SENTIMENT", {})

                    sentiment[symbol] = {
                        "signal": sentiment_data.get("signal", sig.final_signal or "HOLD").upper(),
                        "reason": sentiment_data.get("reason", ""),
                        "updated_at": sig.timestamp.isoformat() if sig.timestamp else None,
                    }

            return sentiment
    except Exception as e:
        logging.error(f"[Dashboard] Failed to load sentiment from database: {e}")
        return {}


# ---------- Routes ----------
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    labels, pnl_data = load_pnl_data()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "labels": labels, "pnl_data": pnl_data},
    )


@router.get("/partial")
async def partial(signal_limit: int = 50):
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

    # Load signals from database - include ALL signals (HOLDs and non-HOLDs)
    signals = []
    try:
        # Fetch more signals to ensure we have enough after filtering
        fetch_limit = min(signal_limit * 3, 500)

        with get_db() as db:
            signal_repo = SignalRepository(db)
            trade_repo = TradeRepository(db)

            # Get recent signals
            recent_signals = signal_repo.get_recent(hours=24, test_mode=False, limit=fetch_limit)

            # Get all trade signal_ids to mark which signals were executed
            executed_signal_ids = set()
            all_trades = trade_repo.get_all(test_mode=False)
            for t in all_trades:
                if t.signal_id:
                    executed_signal_ids.add(t.signal_id)

            # Convert to dict format - include ALL signals
            for s in recent_signals:
                signals.append({
                    "id": s.id,
                    "symbol": s.symbol,
                    "signal": s.final_signal or "HOLD",
                    "confidence": float(s.final_confidence) if s.final_confidence else 0.0,
                    "price": float(s.price) if s.price else 0.0,
                    "timestamp": s.timestamp.isoformat() + 'Z' if s.timestamp else None,
                    "executed": s.id in executed_signal_ids,
                })

            # Limit to most recent signals (filtering handled by UI)
            signals = signals[-signal_limit:]
    except Exception as e:
        logging.error(f"[Partial] Error loading signals from database: {e}")

    return {
        "summary": summary,
        "labels": labels,
        "pnl_data": pnl_data,
        "sentiment": sentiment,
        "trades": real_trades,
        "signals": signals,
    }


@router.get("/status")
async def status():
    status_data = _load_status()
    return JSONResponse(
        {
            "last_status": {
                "time": status_data.get("time"),
                "message": status_data.get("message"),
                "next_run": status_data.get("next_run"),
            },
            "next_run": status_data.get("next_run"),
        }
    )


@router.get("/api/balance")
async def get_balance():
    balance_data = {
        "paper_trading": {
            "initial": 200.0,
            "current": 200.0,
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
        balance_data["paper_trading"]["current"] = round(200.0 + total_pnl, 2)

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
        "balance": balance_data["paper_trading"]["current"],  # UI expects this field
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
    """Get current holdings/positions from database."""
    try:
        # Load holdings directly from database and convert to dict INSIDE session
        with get_db() as db:
            from app.database.repositories import HoldingRepository
            holding_repo = HoldingRepository(db)
            holdings_models = holding_repo.get_current_holdings(test_mode=False)

            # Convert to dict while session is still open
            holdings_list = []
            for h in holdings_models:
                holdings_list.append({
                    "symbol": h.symbol,
                    "amount": float(h.amount),
                    "avg_buy_price": float(h.avg_buy_price),
                    "current_price": float(h.current_price) if h.current_price else float(h.avg_buy_price),
                    "entry_trade_id": h.entry_trade_id,
                    "entry_signal_id": h.entry_signal_id,
                })

        # Get current prices from Kraken
        from app.client.kraken import KrakenClient
        kraken_client = KrakenClient()

        formatted_holdings = {}
        for holding in holdings_list:
            symbol = holding["symbol"]
            amount = holding["amount"]
            avg_price = holding["avg_buy_price"]

            # Get current market price
            try:
                current_price = kraken_client.get_price(symbol)
            except Exception as e:
                logging.warning(f"Failed to get price for {symbol}: {e}")
                current_price = holding["current_price"]

            market_value = amount * current_price
            cost_basis = amount * avg_price
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
                "num_trades": 0,  # Could count from trades if needed
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
    """Get current signals from database."""
    try:
        with get_db() as db:
            repo = SignalRepository(db)
            # Get recent signals (last 24 hours)
            signal_models = repo.get_recent(hours=24, test_mode=False, limit=100)

            # Get most recent signal per symbol
            symbol_signals = {}
            for sig in signal_models:
                symbol = sig.symbol
                if symbol not in symbol_signals:
                    symbol_signals[symbol] = {
                        "id": sig.id,
                        "timestamp": sig.timestamp.isoformat() + 'Z' if sig.timestamp else None,
                        "symbol": sig.symbol,
                        "price": float(sig.price) if sig.price else 0,
                        "final_signal": sig.final_signal,
                        "final_confidence": float(sig.final_confidence) if sig.final_confidence else 0,
                        "aggregation_method": sig.aggregation_method,
                        "strategies": sig.strategies or {},
                    }

            signals_list = list(symbol_signals.values())
            logging.info(f"[Dashboard] Loaded {len(signals_list)} current signals from database")
            return JSONResponse(
                {"signals": signals_list, "count": len(signals_list), "status": "success"}
            )
    except Exception as e:
        logging.error(f"[API] Error in get_current_signals: {e}")
        # Fallback to file-based logger
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
        except Exception as fallback_error:
            logging.error(f"[API] Fallback also failed: {fallback_error}")
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
    """Get strategy performance from database."""
    try:
        lookback_str = request.query_params.get("lookback_days", "7")

        try:
            lookback_days = min(int(lookback_str), 90)
        except ValueError:
            return JSONResponse(
                {"error": "Invalid lookback_days parameter", "status": "error"},
                status_code=400,
            )

        with get_db() as db:
            repo = SignalRepository(db)
            # Get signals from lookback period
            hours = lookback_days * 24
            signals = repo.get_recent(hours=hours, test_mode=False, limit=10000)

            # Calculate performance per strategy
            strategy_stats = defaultdict(lambda: {
                "total_signals": 0,
                "buy_signals": 0,
                "sell_signals": 0,
                "hold_signals": 0,
                "avg_confidence": 0.0,
                "total_confidence": 0.0
            })

            for sig in signals:
                strategies_dict = sig.strategies or {}
                for strategy_name, strategy_data in strategies_dict.items():
                    stats = strategy_stats[strategy_name]
                    stats["total_signals"] += 1

                    signal_type = strategy_data.get("signal", "HOLD") if isinstance(strategy_data, dict) else "HOLD"
                    if signal_type == "BUY":
                        stats["buy_signals"] += 1
                    elif signal_type == "SELL":
                        stats["sell_signals"] += 1
                    else:
                        stats["hold_signals"] += 1

                    confidence = strategy_data.get("confidence", 0) if isinstance(strategy_data, dict) else 0
                    stats["total_confidence"] += confidence

            # Calculate averages
            performance = {}
            for strategy_name, stats in strategy_stats.items():
                if stats["total_signals"] > 0:
                    stats["avg_confidence"] = round(stats["total_confidence"] / stats["total_signals"], 4)
                del stats["total_confidence"]  # Remove intermediate calculation
                performance[strategy_name] = stats

            logging.info(f"[Dashboard] Calculated performance for {len(performance)} strategies from database")
            return JSONResponse(
                {
                    "strategies": performance,
                    "lookback_days": lookback_days,
                    "status": "success",
                }
            )
    except Exception as e:
        logging.error(f"[API] Error in get_strategy_performance: {e}")
        # Fallback to file-based logger
        try:
            performance = signal_logger.get_all_strategies_performance(lookback_days)
            return JSONResponse(
                {
                    "strategies": performance,
                    "lookback_days": lookback_days,
                    "status": "success",
                }
            )
        except Exception as fallback_error:
            logging.error(f"[API] Fallback also failed: {fallback_error}")
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
            # Return 200 with null signal for consistency with other endpoints
            return JSONResponse(
                {"signal": None, "age_seconds": None, "status": "no_data"},
                status_code=200,
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


# Signal Performance Analysis
@router.get("/api/analysis/signal-performance")
async def get_signal_performance():
    """Get comprehensive signal-to-trade correlation and strategy performance analysis."""
    try:
        from app.signal_performance import get_signal_performance_analysis
        analysis = get_signal_performance_analysis()
        return JSONResponse(content=analysis)
    except Exception as e:
        logging.error(f"Error in signal performance analysis: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


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


@router.get("/api/health/details")
async def get_health_details(component: str = None):
    """
    Get detailed health check information for a specific component or all components.

    Query params:
        component: Specific component to check (openai, exchange, rss, database)
                   If not provided, returns details for all components
    """
    try:
        components = {}

        if component is None or component == "openai":
            components["openai"] = await check_openai_health()

        if component is None or component == "exchange":
            components["exchange"] = await check_exchange_health()

        if component is None or component == "rss":
            components["rss"] = await check_rss_feeds_health()

        if component is None or component == "database":
            components["database"] = check_database_health()

        # If specific component requested, return just that one
        if component and component in components:
            return JSONResponse(components[component])
        elif component:
            return JSONResponse(
                {"error": f"Unknown component: {component}"},
                status_code=400
            )

        # Otherwise return all
        return JSONResponse(components)

    except Exception as e:
        logging.error(f"[API] Error in get_health_details: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/errors")
async def get_errors(component: str = None, limit: int = 50):
    """
    Get recent errors, optionally filtered by component.

    Query params:
        component: Filter by component (openai, exchange, rss, database)
        limit: Maximum number of errors to return (default 50)
    """
    try:
        errors = error_tracker.get_errors(component=component, limit=limit)

        return JSONResponse(
            {"errors": errors, "total": len(errors), "component": component}
        )
    except Exception as e:
        logging.error(f"[API] Error fetching errors: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/errors/clear")
async def clear_errors(component: str = None):
    """
    Clear errors, optionally for a specific component.

    Query params:
        component: Optional component name to clear errors for
    """
    try:
        cleared = error_tracker.clear_errors(component=component)

        return JSONResponse(
            {"success": True, "cleared": cleared, "component": component or "all"}
        )
    except Exception as e:
        logging.error(f"[API] Error clearing errors: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/test/openai")
async def test_openai():
    """Test OpenAI API connection."""
    try:
        result = await check_openai_health()

        if result["status"] != "operational":
            error_tracker.log_error(
                component="openai",
                message=f"OpenAI test failed: {result.get('message', 'Unknown error')}",
                severity="warning",
            )

        return JSONResponse(
            {
                "success": result["status"] == "operational",
                "status": result["status"],
                "message": result.get("message", "Test completed"),
                "latency": result.get("latency"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        error_tracker.log_error(
            component="openai",
            message=f"OpenAI test error: {str(e)}",
            error=e,
            severity="error",
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.post("/api/test/kraken")
async def test_kraken():
    """Test Kraken API connection."""
    try:
        result = await check_exchange_health()

        if result["status"] != "operational":
            error_tracker.log_error(
                component="exchange",
                message=f"Kraken test failed: {result.get('message', 'Unknown error')}",
                severity="warning",
            )

        return JSONResponse(
            {
                "success": result["status"] == "operational",
                "status": result["status"],
                "message": result.get("message", "Test completed"),
                "latency": result.get("latency"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        error_tracker.log_error(
            component="exchange",
            message=f"Kraken test error: {str(e)}",
            error=e,
            severity="error",
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.post("/api/test/rss")
async def test_rss():
    """Test RSS feeds connection."""
    try:
        result = await check_rss_feeds_health()

        if result["status"] != "operational":
            error_tracker.log_error(
                component="rss",
                message=f"RSS test failed: {result.get('message', 'Unknown error')}",
                severity="warning",
            )

        return JSONResponse(
            {
                "success": result["status"] == "operational",
                "status": result["status"],
                "message": result.get("message", "Test completed"),
                "latency": result.get("latency"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        error_tracker.log_error(
            component="rss",
            message=f"RSS test error: {str(e)}",
            error=e,
            severity="error",
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.get("/api/health/detailed")
async def get_detailed_health():
    """
    Get detailed health information including errors.

    Returns health status plus recent errors for each component.
    """
    try:
        # Get basic health data
        health_data = {}

        # OpenAI
        openai_status = await check_openai_health()
        openai_errors = error_tracker.get_component_errors("openai")
        health_data["openai"] = {
            "status": openai_status["status"],
            "latency": openai_status.get("latency"),
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errorCount": error_tracker.get_error_count("openai"),
            "lastError": error_tracker.get_last_error("openai"),
            "recentErrors": openai_errors[:5],  # Last 5 errors
        }

        # Kraken/Exchange
        exchange_status = await check_exchange_health()
        exchange_errors = error_tracker.get_component_errors("exchange")
        health_data["exchange"] = {
            "status": exchange_status["status"],
            "latency": exchange_status.get("latency"),
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errorCount": error_tracker.get_error_count("exchange"),
            "lastError": error_tracker.get_last_error("exchange"),
            "recentErrors": exchange_errors[:5],
        }

        # RSS Feeds
        rss_status = await check_rss_feeds_health()
        rss_errors = error_tracker.get_component_errors("rss")
        health_data["rssFeeds"] = {
            "status": rss_status["status"],
            "latency": rss_status.get("latency"),
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errorCount": error_tracker.get_error_count("rss"),
            "lastError": error_tracker.get_last_error("rss"),
            "recentErrors": rss_errors[:5],
        }

        # Database
        db_status = check_database_health()
        db_errors = error_tracker.get_component_errors("database")
        health_data["database"] = {
            "status": db_status["status"],
            "latency": db_status.get("latency"),
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errorCount": error_tracker.get_error_count("database"),
            "lastError": error_tracker.get_last_error("database"),
            "recentErrors": db_errors[:5],
        }

        return JSONResponse(health_data)

    except Exception as e:
        logging.error(f"[API] Error getting detailed health: {e}")
        error_tracker.log_error(
            component="dashboard",
            message=f"Failed to get detailed health: {str(e)}",
            error=e,
        )
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/trades/all")
async def get_all_trades():
    """Get all trades from database."""
    try:
        with get_db() as db:
            repo = TradeRepository(db)
            trade_models = repo.get_all(test_mode=False)

            # Convert to dict format, filter out HOLD actions
            real_trades = []
            for t in trade_models:
                if t.action and t.action.lower() in ("buy", "sell"):
                    real_trades.append({
                        "id": t.id,
                        "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                        "action": t.action,
                        "symbol": t.symbol,
                        "price": float(t.price) if t.price else 0,
                        "amount": float(t.amount) if t.amount else 0,
                        "gross_value": float(t.gross_value) if t.gross_value else 0,
                        "fee": float(t.fee) if t.fee else 0,
                        "net_value": float(t.net_value) if t.net_value else 0,
                        "reason": t.reason,
                        "signal_id": t.signal_id,  # Include signal_id for data integrity tracking
                    })

            logging.info(f"[Dashboard] Loaded {len(real_trades)} trades from database")
            # Wrap in object for consistent API contract
            return {"trades": real_trades}
    except Exception as e:
        logging.error(f"[API] Error loading all trades from database: {e}")
        return JSONResponse([], status_code=500)


"""
Enhanced health check functions for dashboard.py

Replace your existing check_*_health functions with these enhanced versions.
They return detailed error messages and actionable guidance.
"""

async def check_openai_health() -> Dict[str, Any]:
    """Check OpenAI API health with detailed error reporting."""
    try:
        sentiment = load_sentiment()
        if sentiment:
            return {
                "status": "operational",
                "errors": 0,
                "message": "API responding normally",
                "latency": 0
            }
        
        # If no sentiment data, check if API key is configured
        import os
        api_key = os.getenv("OPENAI_API_KEY", "")
        
        if not api_key or api_key == "your-api-key-here":
            return {
                "status": "error",
                "errors": 1,
                "message": "OpenAI API key not configured",
                "details": "Set OPENAI_API_KEY environment variable or update .env file",
                "action": "Add your API key to .env file: OPENAI_API_KEY=sk-...",
                "latency": 0
            }
        
        # Try to make a test API call
        try:
            import openai
            start_time = time.time()
            
            # Test with a minimal API call
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            latency = int((time.time() - start_time) * 1000)
            
            return {
                "status": "operational",
                "errors": 0,
                "message": "API key valid and responding",
                "latency": latency
            }
            
        except openai.AuthenticationError as e:
            return {
                "status": "error",
                "errors": 1,
                "message": "Invalid API key",
                "details": str(e),
                "action": "Verify your OpenAI API key is correct and active",
                "latency": 0
            }
        except openai.RateLimitError as e:
            return {
                "status": "degraded",
                "errors": 1,
                "message": "Rate limit exceeded",
                "details": str(e),
                "action": "Wait 60 seconds and try again, or upgrade your OpenAI plan",
                "latency": 0
            }
        except openai.APIConnectionError as e:
            return {
                "status": "error",
                "errors": 1,
                "message": "Cannot connect to OpenAI API",
                "details": str(e),
                "action": "Check your internet connection and firewall settings",
                "latency": 0
            }
        except Exception as e:
            return {
                "status": "error",
                "errors": 1,
                "message": f"OpenAI API error: {type(e).__name__}",
                "details": str(e),
                "action": "Check OpenAI status page: https://status.openai.com",
                "latency": 0
            }
            
    except Exception as e:
        logging.error(f"[Health] OpenAI check failed: {e}")
        return {
            "status": "error",
            "errors": 1,
            "message": "Health check error",
            "details": str(e),
            "action": "Check application logs for details",
            "latency": 0
        }


async def check_exchange_health() -> Dict[str, Any]:
    """Check Kraken exchange health by testing actual API functionality."""
    try:
        from app.client.kraken import KrakenClient

        start_time = time.time()
        kraken = KrakenClient()

        # Test actual API functionality - get price for BTC
        try:
            price = kraken.get_price("BTCUSD")
            latency = int((time.time() - start_time) * 1000)

            if price > 0:
                return {
                    "status": "operational",
                    "errors": 0,
                    "message": f"Kraken API responding (BTC: ${price:,.2f})",
                    "latency": latency
                }
            else:
                return {
                    "status": "degraded",
                    "errors": 1,
                    "message": "Kraken API returned invalid price",
                    "details": f"Received price: {price}",
                    "action": "Check Kraken API status at https://status.kraken.com",
                    "latency": latency
                }
        except Exception as api_error:
            latency = int((time.time() - start_time) * 1000)
            return {
                "status": "error",
                "errors": 1,
                "message": "Cannot reach Kraken API",
                "details": str(api_error),
                "action": "Check network connection and Kraken status",
                "latency": latency
            }

    except Exception as e:
        logging.error(f"[Health] Exchange check failed: {e}")
        return {
            "status": "error",
            "errors": 1,
            "message": "Exchange health check failed",
            "details": str(e),
            "action": "Check Kraken API credentials and status",
            "latency": 0
        }


async def check_rss_feeds_health() -> Dict[str, Any]:
    """Check RSS feeds health with detailed feed status."""
    try:
        feeds = _load_rss_feeds()
        if not feeds:
            return {
                "status": "error",
                "errors": 1,
                "message": "No RSS feeds configured",
                "details": "No feeds found in database",
                "action": "Add RSS feeds in the Feeds tab",
                "latency": 0
            }

        # Check each feed
        operational_feeds = []
        broken_feeds = []

        import feedparser
        from app.database.repositories import RSSFeedRepository

        # Update errors in database
        with get_db() as db:
            feed_repo = RSSFeedRepository(db)

            for feed in feeds:
                feed_url = feed.get("url", "")
                feed_name = feed.get("name", "Unknown")
                feed_id = feed.get("id")
                is_active = feed.get("active", True)

                if not is_active:
                    continue  # Skip disabled feeds

                error_msg = None

                try:
                    start_time = time.time()
                    parsed = feedparser.parse(feed_url)
                    latency = int((time.time() - start_time) * 1000)

                    if parsed.bozo:  # Feed has errors
                        error_msg = str(parsed.bozo_exception) if hasattr(parsed, 'bozo_exception') else "Parse error"
                        broken_feeds.append({
                            "name": feed_name,
                            "url": feed_url,
                            "error": error_msg
                        })
                    elif len(parsed.entries) == 0:
                        error_msg = "No entries found"
                        broken_feeds.append({
                            "name": feed_name,
                            "url": feed_url,
                            "error": error_msg
                        })
                    else:
                        operational_feeds.append({
                            "name": feed_name,
                            "entries": len(parsed.entries),
                            "latency": latency
                        })
                except Exception as e:
                    error_msg = str(e)
                    broken_feeds.append({
                        "name": feed_name,
                        "url": feed_url,
                        "error": error_msg
                    })

                # Update feed error status in database
                if feed_id:
                    feed_repo.update_fetch_stats(
                        feed_id=feed_id,
                        items_fetched=0 if error_msg else len(parsed.entries) if 'parsed' in locals() else 0,
                        error=error_msg
                    )
        
        total_active = len(operational_feeds) + len(broken_feeds)
        operational_count = len(operational_feeds)
        
        if operational_count == total_active and total_active > 0:
            return {
                "status": "operational",
                "errors": 0,
                "message": f"All {operational_count} feeds operational",
                "details": {
                    "operational": operational_feeds,
                    "broken": []
                },
                "latency": sum(f["latency"] for f in operational_feeds) // len(operational_feeds) if operational_feeds else 0
            }
        elif operational_count > 0:
            return {
                "status": "degraded",
                "errors": len(broken_feeds),
                "message": f"{operational_count}/{total_active} feeds operational",
                "details": {
                    "operational": operational_feeds,
                    "broken": broken_feeds
                },
                "action": f"Fix or disable {len(broken_feeds)} broken feed(s)",
                "latency": sum(f["latency"] for f in operational_feeds) // len(operational_feeds) if operational_feeds else 0
            }
        else:
            return {
                "status": "error",
                "errors": len(broken_feeds),
                "message": f"All {total_active} feeds broken",
                "details": {
                    "operational": [],
                    "broken": broken_feeds
                },
                "action": "Check feed URLs and network connectivity",
                "latency": 0
            }
            
    except Exception as e:
        logging.error(f"[Health] RSS feeds check failed: {e}")
        return {
            "status": "error",
            "errors": 1,
            "message": "RSS health check failed",
            "details": str(e),
            "action": "Check logs for details",
            "latency": 0
        }


def check_database_health() -> Dict[str, Any]:
    """Check SQLite database health."""
    try:
        start_time = time.time()

        with get_db() as db:
            from app.database.repositories import SignalRepository, TradeRepository, HoldingRepository, RSSFeedRepository

            # Test each critical table
            signal_repo = SignalRepository(db)
            trade_repo = TradeRepository(db)
            holding_repo = HoldingRepository(db)
            feed_repo = RSSFeedRepository(db)

            # Count records in each table
            signal_count = len(signal_repo.get_recent(hours=24 * 7, test_mode=False, limit=1000))
            trade_count = len(trade_repo.get_all(test_mode=False))
            holding_count = len(holding_repo.get_current_holdings(test_mode=False))
            feed_count = len(feed_repo.get_all())

            latency = int((time.time() - start_time) * 1000)

            return {
                "status": "operational",
                "errors": 0,
                "message": f"SQLite database operational ({signal_count} signals, {trade_count} trades, {holding_count} holdings, {feed_count} feeds)",
                "latency": latency
            }

    except Exception as e:
        logging.error(f"[Health] Database check failed: {e}")
        latency = int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0
        return {
            "status": "error",
            "errors": 1,
            "message": "Cannot connect to database",
            "details": str(e),
            "action": "Check database file permissions and integrity",
            "latency": latency
        }
# RSS Feed Management


@router.get("/api/errors")
async def get_errors(component: str = None, limit: int = 50):
    """Get recent errors, optionally filtered by component."""
    try:
        errors = error_tracker.get_errors(component=component, limit=limit)
        return JSONResponse({
            "errors": errors,
            "total": len(errors),
            "component": component
        })
    except Exception as e:
        logging.error(f"[API] Error fetching errors: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/errors/clear")
async def clear_errors(component: str = None):
    """Clear errors, optionally for a specific component."""
    try:
        cleared = error_tracker.clear_errors(component=component)
        return JSONResponse({
            "success": True,
            "cleared": cleared,
            "component": component or "all"
        })
    except Exception as e:
        logging.error(f"[API] Error clearing errors: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/test/openai")
async def test_openai():
    """Test OpenAI API connection."""
    try:
        result = await check_openai_health()
        if result["status"] != "operational":
            error_tracker.log_error(
                component="openai",
                message=f"OpenAI test failed: {result.get('message', 'Unknown error')}",
                severity="warning"
            )
        return JSONResponse({
            "success": result["status"] == "operational",
            "status": result["status"],
            "message": result.get("message", "Test completed"),
            "latency": result.get("latency"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        error_tracker.log_error(
            component="openai",
            message=f"OpenAI test error: {str(e)}",
            error=e,
            severity="error"
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.post("/api/test/kraken")
async def test_kraken():
    """Test Kraken API connection."""
    try:
        result = await check_exchange_health()
        if result["status"] != "operational":
            error_tracker.log_error(
                component="exchange",
                message=f"Kraken test failed: {result.get('message', 'Unknown error')}",
                severity="warning"
            )
        return JSONResponse({
            "success": result["status"] == "operational",
            "status": result["status"],
            "message": result.get("message", "Test completed"),
            "latency": result.get("latency"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        error_tracker.log_error(
            component="exchange",
            message=f"Kraken test error: {str(e)}",
            error=e,
            severity="error"
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.post("/api/test/rss")
async def test_rss():
    """Test RSS feeds connection."""
    try:
        result = await check_rss_feeds_health()
        if result["status"] != "operational":
            error_tracker.log_error(
                component="rss",
                message=f"RSS test failed: {result.get('message', 'Unknown error')}",
                severity="warning"
            )
        return JSONResponse({
            "success": result["status"] == "operational",
            "status": result["status"],
            "message": result.get("message", "Test completed"),
            "latency": result.get("latency"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        error_tracker.log_error(
            component="rss",
            message=f"RSS test error: {str(e)}",
            error=e,
            severity="error"
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


# Replace the get_detailed_health endpoint in dashboard.py
# This version passes through ALL fields from health checks (message, details, action, etc.)

# Replace the get_detailed_health endpoint in dashboard.py
# This version passes through ALL fields from health checks (message, details, action, etc.)

@router.get("/api/health/detailed")
async def get_detailed_health():
    """Get detailed health information including errors."""
    try:
        health_data = {}
        
        # OpenAI - merge all fields from health check
        openai_status = await check_openai_health()
        openai_errors = error_tracker.get_component_errors("openai")
        health_data["openai"] = {
            **openai_status,  # This spreads all fields: status, message, details, action, latency
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errorCount": error_tracker.get_error_count("openai"),
            "lastError": error_tracker.get_last_error("openai"),
            "recentErrors": openai_errors[:5]
        }
        
        # Kraken/Exchange - merge all fields
        exchange_status = await check_exchange_health()
        exchange_errors = error_tracker.get_component_errors("exchange")
        health_data["exchange"] = {
            **exchange_status,  # Spreads: status, message, details, action, latency
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errorCount": error_tracker.get_error_count("exchange"),
            "lastError": error_tracker.get_last_error("exchange"),
            "recentErrors": exchange_errors[:5]
        }
        
        # RSS Feeds - merge all fields including details dict
        rss_status = await check_rss_feeds_health()
        rss_errors = error_tracker.get_component_errors("rss")
        health_data["rssFeeds"] = {
            **rss_status,  # Spreads: status, message, details (with operational/broken), action, latency
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errorCount": error_tracker.get_error_count("rss"),
            "lastError": error_tracker.get_last_error("rss"),
            "recentErrors": rss_errors[:5]
        }
        
        # Database - merge all fields
        db_status = check_database_health()
        db_errors = error_tracker.get_component_errors("database")
        health_data["database"] = {
            **db_status,  # Spreads: status, message, details, action, latency
            "lastCheck": datetime.now(timezone.utc).isoformat(),
            "errorCount": error_tracker.get_error_count("database"),
            "lastError": error_tracker.get_last_error("database"),
            "recentErrors": db_errors[:5]
        }
        
        return JSONResponse(health_data)
    except Exception as e:
        logging.error(f"[API] Error getting detailed health: {e}")
        error_tracker.log_error(
            component="dashboard",
            message=f"Failed to get detailed health: {str(e)}",
            error=e
        )
        return JSONResponse(status_code=500, content={"error": str(e)})

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
    """Delete an RSS feed from the database."""
    try:
        with get_db() as db:
            repo = RSSFeedRepository(db)
            feed = repo.get_by_id(feed_id)

            if not feed:
                return JSONResponse(
                    {"error": f"Feed with ID {feed_id} not found", "status": "error"},
                    status_code=404,
                )

            feed_name = feed.name
            success = repo.delete(feed_id)

            if not success:
                return JSONResponse(
                    {"error": "Failed to delete feed", "status": "error"},
                    status_code=500
                )

            db.commit()
            logging.info(f"[Feeds] Deleted feed: {feed_name} (ID: {feed_id})")

            return JSONResponse(
                {"message": "Feed deleted successfully", "id": feed_id, "status": "success"}
            )

    except Exception as e:
        logging.error(f"[API] Error in delete_rss_feed: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


# Configuration Management
@router.get("/api/config")
async def get_config():
    """Get current trading configuration from database."""
    try:
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            bot_config = config_repo.get_current()

            if not bot_config:
                # Return defaults if no config exists
                return JSONResponse({
                    "config": {
                        "trading_mode": "paper",
                        "min_confidence": 0.5,
                        "interval_minutes": 5,
                        "trading_fee_percent": 0.26,
                        "paper_starting_capital": 200,
                        "strategies": {
                            "sentiment": {"enabled": True, "weight": 1.0},
                            "technical": {"enabled": True, "weight": 1.0},
                            "volume": {"enabled": True, "weight": 0.8},
                        },
                        "risk_management": {
                            "position_size_percent": 3.0,
                            "max_daily_loss_percent": 5.0,
                            "max_open_positions": None,
                        },
                        "aggregation": {
                            "method": "weighted_vote",
                            "min_confidence": 0.5
                        },
                    },
                    "status": "success"
                })

            # Convert database config to API format
            config = {
                "trading_mode": bot_config.mode,
                "min_confidence": float(bot_config.min_confidence) if bot_config.min_confidence else 0.5,
                "interval_minutes": 5,  # Fixed for now
                "trading_fee_percent": 0.26,  # Fixed Kraken fee
                "paper_starting_capital": 200,  # Fixed for now
                "strategies": {
                    "sentiment": {"enabled": True, "weight": 1.0},
                    "technical": {"enabled": True, "weight": 1.0},
                    "volume": {"enabled": True, "weight": 0.8},
                },
                "risk_management": {
                    "position_size_percent": 3.0,
                    "max_daily_loss_percent": 5.0,
                    "max_open_positions": None,
                },
                "aggregation": {
                    "method": "weighted_vote",
                    "min_confidence": float(bot_config.min_confidence) if bot_config.min_confidence else 0.5
                },
            }

            return JSONResponse({"config": config, "status": "success"})

    except Exception as e:
        logging.error(f"[API] Error loading config: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.post("/api/config")
async def update_config(request: Request):
    """Update trading configuration - saves to database only."""
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

        # Extract values from the config structure
        mode = new_config.get("trading_mode", "paper")
        min_confidence = new_config.get("aggregation", {}).get("min_confidence", 0.5)
        position_size = new_config.get("risk_management", {}).get("position_size_percent", 5.0)

        # Save to database
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            config_repo.create_or_update(
                mode=mode,
                min_confidence=Decimal(str(min_confidence)),
                position_size=Decimal(str(position_size))
            )
            db.commit()

            logging.info(f"[Config] Saved to database: mode={mode}, min_confidence={min_confidence}, position_size={position_size}")

        return JSONResponse(
            {
                "message": "Configuration updated successfully",
                "config": new_config,
                "status": "success",
            }
        )

    except Exception as e:
        logging.error(f"[API] Error updating config: {e}")
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@router.put("/api/feeds/{feed_id}")
async def update_rss_feed(feed_id: int, request: Request):
    """Update an RSS feed in the database."""
    try:
        body = await request.json()

        with get_db() as db:
            repo = RSSFeedRepository(db)
            feed = repo.get_by_id(feed_id)

            if not feed:
                return JSONResponse(
                    {"error": f"Feed with ID {feed_id} not found", "status": "error"},
                    status_code=404,
                )

            # Update only the allowed fields
            update_data = {}
            if "name" in body:
                update_data["name"] = body["name"]
            if "url" in body:
                update_data["url"] = body["url"]
            if "enabled" in body:
                update_data["enabled"] = body["enabled"]
            if "keywords" in body:
                update_data["keywords"] = body["keywords"]

            if update_data:
                repo.update(feed_id, **update_data)
                db.commit()

            logging.info(f"[Feeds] Updated feed ID {feed_id} ({feed.name})")

            # Return updated feed data
            updated_feed = repo.get_by_id(feed_id)
            return JSONResponse(
                {
                    "message": "Feed updated successfully",
                    "feed": {
                        "id": updated_feed.id,
                        "name": updated_feed.name,
                        "url": updated_feed.url,
                        "enabled": updated_feed.enabled,
                        "keywords": updated_feed.keywords or []
                    },
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
        with get_db() as db:
            repo = RSSFeedRepository(db)
            feed = repo.get_by_id(feed_id)

            if feed is None:
                return JSONResponse(
                    status_code=404, content={"error": f"Feed ID {feed_id} not found"}
                )

            # Toggle the enabled field
            new_status = not feed.enabled
            repo.update(feed_id, enabled=new_status)
            db.commit()

            status_text = "enabled" if new_status else "disabled"
            logging.info(f"[Feeds] Toggled feed ID {feed_id} ({feed.name}): {status_text}")

            return {"success": True, "active": new_status, "feed_id": feed_id}

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
            return JSONResponse(status_code=400, content={"error": "Feed has no URL"})

        parsed = feedparser.parse(url)

        if parsed.bozo:
            error_msg = (
                str(parsed.bozo_exception)
                if hasattr(parsed, "bozo_exception")
                else "Invalid feed"
            )
            return JSONResponse(
                status_code=400, content={"error": error_msg, "status": "error"}
            )

        entry_count = len(parsed.entries)
        title = parsed.feed.get("title", "Unknown")

        return {
            "status": "success",
            "entries": entry_count,
            "title": title,
            "message": f"Feed OK - {entry_count} entries found",
        }
    except Exception as e:
        logging.error(f"[Feeds] Error testing feed {feed_id}: {e}")
        return JSONResponse(
            status_code=500, content={"error": str(e), "status": "error"}
        )


# ===================================
# Server-Sent Events (SSE) for real-time updates
# ===================================

@router.get("/api/events")
async def event_stream(request: Request):
    """
    Server-Sent Events endpoint for real-time updates.
    Clients can subscribe to this endpoint to receive live updates.
    """
    async def event_generator():
        """Generate SSE events."""
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'message': 'Event stream connected'})}\n\n"

        # Queue to receive events
        event_queue = asyncio.Queue()

        # Subscribe to all event types
        async def on_event(event):
            await event_queue.put(event)

        for event_type in EventType:
            event_bus.subscribe(event_type, on_event)

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logging.info("[SSE] Client disconnected")
                    break

                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                    # Send event to client
                    yield f"data: {json.dumps(event)}\n\n"

                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f": heartbeat\n\n"

        except asyncio.CancelledError:
            logging.info("[SSE] Event stream cancelled")
        finally:
            # Unsubscribe from events
            for event_type in EventType:
                event_bus.unsubscribe(event_type, on_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# ===================================
# Theme Management
# ===================================

@router.get("/api/theme")
async def get_theme():
    """Get current theme settings."""
    # For now, return default theme
    # In future, could store user preference in database
    return {
        "current": "dark",
        "available": ["light", "dark", "auto"]
    }


@router.post("/api/theme")
async def set_theme(request: Request):
    """Set theme preference."""
    data = await request.json()
    theme = data.get("theme", "dark")

    # TODO: Store theme preference in database or session
    # For now, just return success
    return {"status": "success", "theme": theme}
