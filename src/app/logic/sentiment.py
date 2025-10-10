import logging
import os
import json
import re
import openai
from dotenv import load_dotenv

load_dotenv()


class SentimentSignal:
    def __init__(self):
        self.model = "gpt-4o-mini"
        # Initialize client lazily
        self._client = None
    
    @property
    def client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._client = openai.OpenAI(api_key=api_key)
            else:
                # For testing without API key
                self._client = openai.OpenAI(api_key="dummy-key-for-testing")
        return self._client

    # ---------- Fallback quick sentiment ----------
    def _fallback_parse(self, headline: str):
        """
        Heuristic sentiment detector for obvious signals.
        Returns (signal, reason) or None if inconclusive.
        """
        text = headline.lower()

        positive_keywords = [
            "surge", "soar", "record high", "all-time high",
            "bullish", "rally", "partnership", "adoption", "gain"
        ]
        negative_keywords = [
            "plunge", "collapse", "lawsuit", "ban",
            "hack", "bearish", "drop", "loss", "decline"
        ]

        if any(word in text for word in positive_keywords):
            return "BUY", f"Keyword match (positive): {headline}"
        if any(word in text for word in negative_keywords):
            return "SELL", f"Keyword match (negative): {headline}"

        return None  # no obvious hit

    # ---------- Single headline ----------
    def get_signal(self, headline: str, symbol: str):
        # First try fallback
        fallback = self._fallback_parse(headline)
        if fallback:
            return fallback

        # Then try GPT
        try:
            prompt = (
                f'Given the headline: "{headline}" and the crypto symbol {symbol}, '
                f"determine the most appropriate trading signal from the options: BUY, HOLD, or SELL. "
                f"Also explain briefly why. Your output should be a JSON object like: "
                f'{{\"signal\": \"BUY\", \"reason\": \"High interest and positive news.\"}}'
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=100,
            )

            content = response.choices[0].message.content.strip()
            result = json.loads(content)

            signal = result.get("signal", "HOLD").upper()
            reason = result.get("reason", "No reason provided.")
            if signal not in ["BUY", "SELL", "HOLD"]:
                signal = "HOLD"

            return signal, reason

        except Exception as e:
            logging.error(f"[SentimentSignal] GPT error for {symbol}: {e}")
            return "HOLD", f"GPT error: {e}"

    # ---------- Multi headline ----------
    def get_signals(self, headlines: list[str], symbol: str):
        if not headlines:
            return "HOLD", "No headlines provided."

        # If any headline triggers fallback, bias result toward that signal
        fallback_hits = [self._fallback_parse(h) for h in headlines]
        fallback_hits = [h for h in fallback_hits if h]
        if fallback_hits:
            # Prioritize SELL > BUY > HOLD
            for sig, reason in fallback_hits:
                if sig == "SELL":
                    return sig, reason
            for sig, reason in fallback_hits:
                if sig == "BUY":
                    return sig, reason

        # Otherwise consolidate via GPT
        try:
            prompt = (
                f"You are analyzing sentiment for {symbol}. "
                f"Here are recent headlines:\n"
                + "\n".join([f"- {h}" for h in headlines])
                + "\n\nBased on these, output a JSON object like: "
                '{"signal": "BUY"|"SELL"|"HOLD", "reason": "brief explanation"}.\n'
                "If the sentiment is mixed, prefer HOLD."
            )

            logging.info(f"[SentimentSignal] Sending {len(headlines)} headlines for {symbol} to GPT")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150,
            )

            content = response.choices[0].message.content.strip()
            result = json.loads(content)

            signal = result.get("signal", "HOLD").upper()
            reason = result.get("reason", "No reason provided.")
            if signal not in ["BUY", "SELL", "HOLD"]:
                signal = "HOLD"

            logging.info(f"[SentimentSignal] {symbol} consolidated signal: {signal} — {reason}")
            return signal, reason

        except Exception as e:
            logging.error(f"[SentimentSignal] GPT error for {symbol}: {e}")
            return "HOLD", f"GPT error: {e}"
