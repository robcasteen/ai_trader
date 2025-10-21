cd ~/kraken-ai-bot
git add .
git commit -m "Fix scanner to use configurable priority symbols instead of volume

- Scanner was returning 0 symbols due to Kraken API format change
- Kraken no longer accepts {\"pair\": \"all\"}, just call Ticker with no params
- Memecoins have massive volume, drowning out major cryptos
- Add DEFAULT_PRIORITY_SYMBOLS for major cryptos (BTC, ETH, XRP, etc.)
- Make scanner configurable via priority_symbols parameter
- Empty list [] falls back to volume-based sorting
- Add 7 new tests for configurable scanner behavior
- Fix dashboard status polling (was only loading once, now polls every 5s)
- Fix timezone display issue (was showing 3 hours stale)
- All 335 Python + 3 JS tests passing

Learnings:
- Kraken API changed format, removed support for pair=\"all\"
- Volume sorting unreliable - memecoins dominate real trading volume
- Priority/whitelist approach more reliable for production trading
- TDD caught the issue early and guided the refactor
- Configuration > hardcoding for production systems"

git push