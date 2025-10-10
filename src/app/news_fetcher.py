import feedparser
import json
import os
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # /src/app
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

NEWS_FILE = LOGS_DIR / "seen_news.json"


def get_rss_feeds():
    return [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
        "https://cryptopotato.com/feed/",
    ]


def get_headline_hash(headline: str) -> str:
    return hashlib.sha256(headline.encode()).hexdigest()


def load_seen() -> dict:
    if not NEWS_FILE.exists():
        return {}
    try:
        with open(NEWS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_seen(seen: dict):
    with open(NEWS_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def extract_symbol_from_headline(headline: str) -> str | None:
    headline = headline.upper()
    for symbol in [
        "BTC",
        "ETH",
        "SOL",
        "XRP",
        "ADA",
        "DOGE",
        "AVAX",
        "MATIC",
        "LTC",
        "AAVE",
        "LINK",
        "1INCH",
        "UNI",
        "XLM",
        "ATOM",
        "DOT",
        "SHIB",
        "TRX",
    ]:
        if symbol in headline:
            return f"{symbol}USD"
    return None


def get_unseen_headlines() -> dict[str, list[str]]:
    """
    Returns dict: symbol -> [list of unseen headlines].
    """
    seen = load_seen()
    unseen: dict[str, list[str]] = {}

    for url in get_rss_feeds():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            headline = entry.title.strip()
            symbol = extract_symbol_from_headline(headline)
            if not symbol:
                continue

            headline_hash = get_headline_hash(headline)
            if headline_hash not in seen.get(symbol, []):
                unseen.setdefault(symbol, []).append(headline)

    return unseen


def mark_as_seen(symbol: str, headlines: list[str]):
    """
    Mark these headlines for `symbol` as seen.
    Keeps only last 50 hashes per symbol.
    """
    seen = load_seen()
    if symbol not in seen:
        seen[symbol] = []

    for h in headlines:
        hhash = get_headline_hash(h)
        if hhash not in seen[symbol]:
            seen[symbol].append(hhash)

    # keep only last 50
    seen[symbol] = seen[symbol][-50:]
    save_seen(seen)
