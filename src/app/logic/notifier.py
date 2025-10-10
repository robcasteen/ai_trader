import logging

class Notifier:
    def send(self, trade_result):
        # Currently logs only. Extend with Telegram/email/etc. later.
        if not trade_result:
            return

        symbol = trade_result.get("symbol", "?")
        action = trade_result.get("action", "HOLD")
        price = trade_result.get("price", 0)
        reason = trade_result.get("reason", "No reason.")

        logging.info(f"[ALERT] [{symbol}] {action} @ {price} — {reason}")
