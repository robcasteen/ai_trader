"""
Telegram notification module for trade alerts.
"""
import os
import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
import requests


class TelegramNotifier:
    """Send trade notifications via Telegram."""

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logging.warning(
                "[Telegram] Notifications disabled: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
            )

    def send_trade_notification(
        self,
        action: str,
        symbol: str,
        amount: Decimal,
        price: Decimal,
        gross_value: Decimal,
        fee: Decimal,
        net_value: Decimal,
        balance_before: Optional[Decimal] = None,
        balance_after: Optional[Decimal] = None,
        reason: Optional[str] = None,
        pnl: Optional[Decimal] = None,
        pnl_percentage: Optional[float] = None,
        total_trades: Optional[int] = None,
        win_rate: Optional[float] = None,
        test_mode: bool = False
    ) -> bool:
        """
        Send a trade notification to Telegram.

        Args:
            action: BUY or SELL
            symbol: Trading pair (e.g., BTCUSD)
            amount: Amount of asset traded
            price: Price per unit
            gross_value: Total value before fees
            fee: Trading fee
            net_value: Total value after fees
            balance_before: Balance before trade
            balance_after: Balance after trade
            reason: Reason for the trade
            pnl: Profit/loss for this trade
            pnl_percentage: PnL as percentage
            total_trades: Total number of trades
            win_rate: Win rate percentage
            test_mode: Whether this is a test trade

        Returns:
            True if notification sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            # Build the message
            emoji = "🟢" if action == "BUY" else "🔴"
            mode_badge = "🧪 TEST MODE" if test_mode else "💰 LIVE"

            message = f"{emoji} *{mode_badge} - {action} {symbol}*\n\n"

            # Trade details
            message += f"📊 *Trade Details:*\n"
            message += f"• Amount: `{amount:.8f}` {symbol[:3]}\n"
            message += f"• Price: `${price:,.2f}`\n"
            message += f"• Gross Value: `${gross_value:,.2f}`\n"
            message += f"• Fee: `${fee:,.2f}`\n"
            message += f"• Net Value: `${net_value:,.2f}`\n"

            # Balance info
            if balance_before is not None and balance_after is not None:
                balance_change = balance_after - balance_before
                change_emoji = "📈" if balance_change >= 0 else "📉"
                message += f"\n💵 *Balance:*\n"
                message += f"• Before: `${balance_before:,.2f}`\n"
                message += f"• After: `${balance_after:,.2f}`\n"
                message += f"• Change: {change_emoji} `${balance_change:+,.2f}`\n"

            # PnL info
            if pnl is not None:
                pnl_emoji = "✅" if pnl >= 0 else "❌"
                message += f"\n{pnl_emoji} *Performance:*\n"
                message += f"• P/L: `${pnl:+,.2f}`"
                if pnl_percentage is not None:
                    message += f" ({pnl_percentage:+.2f}%)"
                message += "\n"

            # Trading stats
            if total_trades is not None or win_rate is not None:
                message += f"\n📈 *Stats:*\n"
                if total_trades is not None:
                    message += f"• Total Trades: `{total_trades}`\n"
                if win_rate is not None:
                    message += f"• Win Rate: `{win_rate:.1f}%`\n"

            # Reason
            if reason:
                message += f"\n💡 *Reason:* {reason}\n"

            # Timestamp
            message += f"\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"

            # Send via Telegram API
            return self._send_message(message)

        except Exception as e:
            logging.error(f"[Telegram] Failed to send trade notification: {e}")
            return False

    def send_error_notification(self, error_message: str, context: Optional[str] = None) -> bool:
        """Send an error notification."""
        if not self.enabled:
            return False

        try:
            message = f"🚨 *Bot Error Alert*\n\n"
            message += f"❌ {error_message}\n"

            if context:
                message += f"\n📝 Context: {context}\n"

            message += f"\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"

            return self._send_message(message)

        except Exception as e:
            logging.error(f"[Telegram] Failed to send error notification: {e}")
            return False

    def send_status_notification(self, status: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Send a status update notification."""
        if not self.enabled:
            return False

        try:
            message = f"ℹ️ *Bot Status Update*\n\n"
            message += f"{status}\n"

            if details:
                message += f"\n📋 *Details:*\n"
                for key, value in details.items():
                    message += f"• {key}: `{value}`\n"

            message += f"\n🕐 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"

            return self._send_message(message)

        except Exception as e:
            logging.error(f"[Telegram] Failed to send status notification: {e}")
            return False

    def _send_message(self, text: str) -> bool:
        """Send a message to Telegram using the Bot API."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logging.info("[Telegram] Notification sent successfully")
                return True
            else:
                logging.error(
                    f"[Telegram] Failed to send notification: "
                    f"Status {response.status_code}, Response: {response.text}"
                )
                return False

        except requests.exceptions.Timeout:
            logging.error("[Telegram] Request timed out")
            return False
        except Exception as e:
            logging.error(f"[Telegram] Error sending message: {e}")
            return False


# Global instance
_notifier = None

def get_telegram_notifier() -> TelegramNotifier:
    """Get or create the global TelegramNotifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
