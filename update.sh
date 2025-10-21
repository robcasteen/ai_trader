# Stage all changes
cd ~/kraken-ai-bot
git add -A

# Commit with detailed message
git commit -m "feat: Symbol normalization and holdings tracking

- Added symbol normalizer supporting 17 major cryptocurrencies
- Fixed holdings tracking bug (trades now update holdings automatically)
- Migrated 5,348 historical trades to canonical format
- All 314 tests passing including 7 new normalization tests
- Clean data: 9 positions, $9,871 market value, +$163 unrealized P&L

Files added:
- src/app/utils/symbol_normalizer.py (normalization logic)
- tests/test_symbol_normalizer.py (17 tests)
- tests/test_paper_trader_symbol_normalization.py (7 integration tests)
- scripts/migrate_symbols.py (data migration script)

Files modified:
- src/app/logic/paper_trader.py (added normalization + holdings update)
- tests/test_paper_trader.py (updated for canonical symbols)

Breaking changes:
- All symbols now stored in canonical format (BTCUSD not BTC/USD)
- Holdings rebuild required after update (migration script provided)"

# Push to remote
git push origin main

# Show status
git log --oneline -5
git status