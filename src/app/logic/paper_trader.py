import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from app.utils.symbol_normalizer import normalize_symbol
from app.notifications.telegram import get_telegram_notifier
from app.database.connection import get_db
from app.database.repositories import TradeRepository, HoldingRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
# REMOVED: TRADES_FILE and HOLDINGS_FILE - all data now in database


class PaperTrader:
    def __init__(self):
        # REMOVED: JSON file initialization - all data now in database
        pass

    def get_holdings(self):
        """Get current holdings/positions from database."""
        try:
            with get_db() as db:
                holding_repo = HoldingRepository(db)
                holdings_list = holding_repo.get_current_holdings(test_mode=False)

                # Convert to dict format for compatibility
                holdings_dict = {}
                for holding in holdings_list:
                    amount = float(holding.amount)
                    avg_price = float(holding.avg_buy_price)
                    current_price = float(holding.current_price) if holding.current_price else avg_price

                    holdings_dict[holding.symbol] = {
                        "amount": amount,
                        "avg_price": avg_price,
                        "current_price": current_price,
                        "market_value": amount * current_price,
                        "cost_basis": amount * avg_price,
                        "unrealized_pnl": float(holding.unrealized_pnl) if holding.unrealized_pnl else 0.0,
                    }
                return holdings_dict
        except Exception as e:
            logging.error(f"[PaperTrader] Failed to load holdings from database: {e}")
            return {}

    def update_holdings(self, symbol, action, amount, price, trade_id=None, signal_id=None):
        """Update holdings in database based on trade action.

        Args:
            symbol: Trading symbol
            action: BUY or SELL
            amount: Trade amount
            price: Trade price
            trade_id: Database ID of the trade that created/modified this holding
            signal_id: Database ID of the signal that triggered the trade
        """
        # Normalize symbol to canonical format
        canonical_symbol = normalize_symbol(symbol)

        try:
            with get_db() as db:
                holding_repo = HoldingRepository(db)
                holdings = self.get_holdings()

                if action.upper() == "BUY":
                    if canonical_symbol in holdings:
                        # Average up position
                        old_amount = holdings[canonical_symbol]["amount"]
                        old_avg_price = holdings[canonical_symbol]["avg_price"]
                        new_amount = old_amount + amount
                        new_avg_price = (
                            (old_amount * old_avg_price) + (amount * price)
                        ) / new_amount

                        # Update holding in database - preserving original entry IDs for averaging up
                        holding_repo.create(
                            timestamp=datetime.now(timezone.utc),
                            symbol=canonical_symbol,
                            amount=Decimal(str(new_amount)),
                            avg_buy_price=Decimal(str(new_avg_price)),
                            current_price=Decimal(str(price)),
                            unrealized_pnl=Decimal(str((new_amount * price) - (new_amount * new_avg_price))),
                            entry_trade_id=trade_id,  # Link to current trade for averaging up
                            entry_signal_id=signal_id,  # Link to current signal
                            test_mode=False
                        )
                    else:
                        # New position - link to originating trade and signal
                        holding_repo.create(
                            timestamp=datetime.now(timezone.utc),
                            symbol=canonical_symbol,
                            amount=Decimal(str(amount)),
                            avg_buy_price=Decimal(str(price)),
                            current_price=Decimal(str(price)),
                            unrealized_pnl=Decimal("0.0"),
                            entry_trade_id=trade_id,  # Link to originating trade
                            entry_signal_id=signal_id,  # Link to originating signal
                            test_mode=False
                        )

                elif action.upper() == "SELL":
                    if canonical_symbol in holdings:
                        new_amount = holdings[canonical_symbol]["amount"] - amount

                        # Always create a holding record to update the position
                        # If position closed, amount will be 0 (filtered by get_current_holdings)
                        if new_amount < 0:
                            new_amount = 0  # Can't go negative

                        avg_price = holdings[canonical_symbol]["avg_price"]
                        market_value = new_amount * price
                        cost_basis = new_amount * avg_price
                        unrealized_pnl = market_value - cost_basis

                        holding_repo.create(
                            timestamp=datetime.now(timezone.utc),
                            symbol=canonical_symbol,
                            amount=Decimal(str(new_amount)),
                            avg_buy_price=Decimal(str(avg_price)),
                            current_price=Decimal(str(price)),
                            unrealized_pnl=Decimal(str(unrealized_pnl)),
                            entry_trade_id=trade_id,  # Link to trade that reduced position
                            entry_signal_id=signal_id,  # Link to signal
                            test_mode=False
                        )

                db.commit()
                logging.info(f"[PaperTrader] Updated holdings in database: {action} {canonical_symbol}")

        except Exception as e:
            logging.error(f"[PaperTrader] Failed to update holdings in database: {e}")

    def execute_trade(self, symbol, action, price, balance, reason, amount=0.01, signal_id=None):
        """
        Simulate a trade with Kraken fees.
        - Taker fee: 0.26% applied to all trades
        - Fees reduce the effective value for both buys and sells

        For BUY: You pay price + fee
        For SELL: You receive price - fee
        For HOLD: No trade executed

        Args:
            signal_id: The database ID of the signal that triggered this trade (for correlation)
        """
        # Normalize symbol to canonical format
        canonical_symbol = normalize_symbol(symbol)
        
        # Handle HOLD - do not execute trade
        if action.upper() == "HOLD":
            return {
                "success": True,
                "action": "HOLD",
                "symbol": canonical_symbol,
                "message": "No trade executed - HOLD signal",
                "reason": reason
            }
        
        # Validate action
        if action.upper() not in ["BUY", "SELL"]:
            return {
                "success": False,
                "action": action,
                "symbol": canonical_symbol,
                "message": f"Invalid action: {action}",
                "reason": reason
            }

        # Validate SELL - check if position exists
        if action.upper() == "SELL":
            holdings = self.get_holdings()
            if canonical_symbol not in holdings or holdings[canonical_symbol]["amount"] <= 0:
                return {
                    "success": False,
                    "action": "SELL",
                    "symbol": canonical_symbol,
                    "message": "Cannot sell - no position exists",
                    "reason": reason
                }

        # Calculate gross value
        gross_value = amount * price
        
        # Apply 0.26% taker fee (always reduces net proceeds)
        fee_rate = 0.0026
        fee = gross_value * fee_rate
        
        # Net value calculation (fee always reduces what you get/pay)
        # BUY: Total cost = gross_value + fee (you pay MORE)
        # SELL: Total proceeds = gross_value - fee (you receive LESS)
        if action.lower() == "buy":
            net_value = gross_value + fee  # Cost includes fee
        elif action.lower() == "sell":
            net_value = gross_value - fee  # Proceeds minus fee
        else:
            # Should never reach here due to validation above
            return {
                "success": False,
                "action": action,
                "symbol": canonical_symbol,
                "message": f"Unexpected action: {action}"
            }
        
        # Write trade to database with signal_id
        trade_id = None
        try:
            with get_db() as db:
                repo = TradeRepository(db)
                trade_model = repo.create(
                    timestamp=datetime.now(timezone.utc),
                    action=action.lower(),
                    symbol=canonical_symbol,
                    price=price,
                    amount=amount,
                    gross_value=gross_value,
                    fee=fee,
                    net_value=net_value,
                    reason=reason,
                    test_mode=False,
                    signal_id=signal_id  # Link trade to triggering signal
                )
                db.flush()  # Ensure trade ID is available
                trade_id = trade_model.id
                db.commit()
                logging.info(f"[PaperTrader] Saved trade to database: ID={trade_id}, {action} {canonical_symbol} | signal_id={signal_id}")

                # Emit TRADE_EXECUTED event to event bus for SSE
                try:
                    import asyncio
                    from app.events.event_bus import event_bus, EventType

                    # Run emit in background if there's an event loop, otherwise skip
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(event_bus.emit(EventType.TRADE_EXECUTED, {
                                "trade_id": trade_id,
                                "symbol": canonical_symbol,
                                "action": action.lower(),
                                "price": price,
                                "amount": amount,
                                "net_value": net_value,
                                "signal_id": signal_id,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }))
                        else:
                            # No running loop, run it synchronously
                            loop.run_until_complete(event_bus.emit(EventType.TRADE_EXECUTED, {
                                "trade_id": trade_id,
                                "symbol": canonical_symbol,
                                "action": action.lower(),
                                "price": price,
                                "amount": amount,
                                "net_value": net_value,
                                "signal_id": signal_id,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }))
                    except RuntimeError:
                        # No event loop exists, create one
                        asyncio.run(event_bus.emit(EventType.TRADE_EXECUTED, {
                            "trade_id": trade_id,
                            "symbol": canonical_symbol,
                            "action": action.lower(),
                            "price": price,
                            "amount": amount,
                            "net_value": net_value,
                            "signal_id": signal_id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }))
                except Exception as e:
                    logging.error(f"[PaperTrader] Failed to emit TRADE_EXECUTED event: {e}")

        except Exception as e:
            logging.error(f"[PaperTrader] Failed to save trade to database: {e}")

        # Create trade dict for return and notifications
        trade = {
            "timestamp": datetime.now().isoformat(),
            "action": action.lower(),
            "symbol": canonical_symbol,
            "price": price,
            "amount": amount,
            "gross_value": round(gross_value, 2),
            "fee": round(fee, 2),
            "net_value": round(net_value, 2),
            "reason": reason,
            "value": round(net_value, 2),
        }

        # Update holdings after trade executes - pass trade_id and signal_id for data integrity
        self.update_holdings(canonical_symbol, action, amount, price, trade_id=trade_id, signal_id=signal_id)

        # Send Telegram notification
        try:
            self._send_trade_notification(
                trade=trade,
                balance_before=balance,
                canonical_symbol=canonical_symbol
            )
        except Exception as e:
            logging.error(f"[PaperTrader] Failed to send Telegram notification: {e}")

        # Return trade dict for backward compatibility
        return trade

    def _send_trade_notification(self, trade: dict, balance_before: float, canonical_symbol: str):
        """Send Telegram notification for executed trade."""
        notifier = get_telegram_notifier()
        if not notifier.enabled:
            return

        # Calculate balance after trade
        action = trade["action"].upper()
        net_value = trade["net_value"]

        if action == "BUY":
            balance_after = balance_before - net_value
        else:  # SELL
            balance_after = balance_before + net_value

        # Calculate PnL for SELL trades
        pnl = None
        pnl_percentage = None
        if action == "SELL":
            holdings = self.get_holdings()
            if canonical_symbol in holdings:
                avg_buy_price = holdings[canonical_symbol]["avg_price"]
                sell_price = trade["price"]
                pnl = (sell_price - avg_buy_price) * trade["amount"]
                pnl_percentage = ((sell_price - avg_buy_price) / avg_buy_price) * 100

        # Calculate trading stats
        total_trades = self._get_trade_count()
        win_rate = self._calculate_win_rate()

        # Send notification
        notifier.send_trade_notification(
            action=action,
            symbol=trade["symbol"],
            amount=Decimal(str(trade["amount"])),
            price=Decimal(str(trade["price"])),
            gross_value=Decimal(str(trade["gross_value"])),
            fee=Decimal(str(trade["fee"])),
            net_value=Decimal(str(trade["net_value"])),
            balance_before=Decimal(str(balance_before)),
            balance_after=Decimal(str(balance_after)),
            reason=trade.get("reason"),
            pnl=Decimal(str(pnl)) if pnl is not None else None,
            pnl_percentage=pnl_percentage,
            total_trades=total_trades,
            win_rate=win_rate,
            test_mode=False
        )

    def _get_trade_count(self) -> int:
        """Get total number of trades executed from database."""
        try:
            with get_db() as db:
                repo = TradeRepository(db)
                trades = repo.get_all(test_mode=False)
                return len([t for t in trades if t.action and t.action.lower() != "hold"])
        except Exception as e:
            logging.error(f"[PaperTrader] Failed to get trade count from database: {e}")
            return 0

    def _calculate_win_rate(self) -> Optional[float]:
        """Calculate win rate from sell trades in database."""
        try:
            with get_db() as db:
                repo = TradeRepository(db)
                trades = repo.get_all(test_mode=False)

            # Track buy and sell prices for each symbol
            positions = {}
            wins = 0
            total_sells = 0

            for trade in trades:
                symbol = trade.symbol
                action = (trade.action or "").upper()
                price = float(trade.price) if trade.price else 0

                if action == "BUY":
                    if symbol not in positions:
                        positions[symbol] = []
                    positions[symbol].append(price)

                elif action == "SELL" and symbol in positions and positions[symbol]:
                    # Use average buy price
                    avg_buy = sum(positions[symbol]) / len(positions[symbol])
                    if price > avg_buy:
                        wins += 1
                    total_sells += 1
                    positions[symbol] = []  # Clear position

            if total_sells == 0:
                return None

            return (wins / total_sells) * 100

        except Exception as e:
            logging.error(f"[PaperTrader] Failed to calculate win rate from database: {e}")
            return None 