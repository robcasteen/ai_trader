# 🔧 PHASE 1.5 - CRITICAL ISSUES TO RESOLVE

**Status:** Dashboard working, but core functionality needs fixes before Phase 2  
**Priority:** HIGH - These block backtesting and production use

---

## 🚨 BLOCKING ISSUES

### 1. System Status Display Incorrect
**Current State:** System Status panel showing incorrect/stale data  
**Location:** Dashboard Overview tab → System Status panel  
**Elements affected:**
- LAST RUN: Shows "--" or wrong time
- NEXT RUN: Shows "--" or wrong time  
- MESSAGE: Shows "--" or generic message

**Expected behavior:**
- LAST RUN: Actual timestamp of last `run_trade_cycle()` execution
- NEXT RUN: Next scheduled run time (should be ~5 minutes from last run)
- MESSAGE: Meaningful status (e.g., "Completed 5 trades" or "No signals generated")

**Investigation needed:**
```bash
# Check if bot_status.json is being written
cat src/app/logs/bot_status.json | jq

# Check if /status endpoint returns correct data
curl http://localhost:8000/status | jq

# Check main.py - is status being updated in run_trade_cycle()?
grep -A 20 "def run_trade_cycle" src/app/main.py | grep status
```

**Files to check:**
- `src/app/main.py` - Does `run_trade_cycle()` write to STATUS_FILE?
- `src/app/dashboard.py` - Does `/status` endpoint read STATUS_FILE correctly?
- `src/static/js/dashboard.js` - Does `loadStatus()` update the right element IDs?

---

### 2. Strategy Manager Not Using All Strategies
**Current State:** Only sentiment strategy is running  
**Expected:** Technical, Volume, AND Sentiment should all evaluate and compete  

**Symptoms:**
- Strategy signals only show "sentiment: ..." in reasoning
- No technical indicators (SMA, RSI, momentum) in signals
- No volume analysis in signals

**Root cause investigation:**
```bash
# Check strategy_manager initialization
grep -A 10 "StrategyManager" src/app/main.py

# Check strategy config
grep -B 5 -A 15 "strategy_config" src/app/main.py

# Are technical and volume strategies enabled?
# Should see:
# "use_technical": True,
# "use_volume": True,
# "use_sentiment": True,
```

**Expected behavior:**
- Each symbol gets evaluated by ALL enabled strategies
- Final signal is weighted vote/consensus of all strategies
- Strategy signals should show all 3 strategies in reasoning:
```json
  {
    "strategies": {
      "technical": {"signal": "BUY", "confidence": 0.7, "reason": "..."},
      "volume": {"signal": "HOLD", "confidence": 0.5, "reason": "..."},
      "sentiment": {"signal": "BUY", "confidence": 0.8, "reason": "..."}
    },
    "final_signal": "BUY",
    "confidence": 0.75
  }
```

**Files to fix:**
- `src/app/main.py` - Verify strategy_config has all strategies enabled
- `src/strategies/strategy_manager.py` - Check aggregation logic
- `src/strategies/technical_strategy.py` - Verify it's getting called
- `src/strategies/volume_strategy.py` - Verify it's getting called

**Quality check:**
After fix, check `strategy_signals.jsonl`:
```bash
tail -5 src/app/logs/strategy_signals.jsonl | jq '.strategies | keys'
# Should show: ["sentiment", "technical", "volume"]
```

---

### 3. RSS Feed Management Issues
**Current State:** Feed test/delete buttons don't work correctly  
**Missing features:** Cannot edit or disable feeds without deleting

**Specific problems:**

#### 3A. Test Feed Button Not Working
**Symptom:** Clicking TEST does nothing or shows error  
**Expected:** Should test fetch feed and show headline count

**Check:**
```bash
# Does endpoint exist?
curl -X POST http://localhost:8000/api/feeds/test \
  -H "Content-Type: application/json" \
  -d '{"url": "https://cointelegraph.com/rss"}'

# Check dashboard.js testFeed function
grep -A 20 "async function testFeed" src/static/js/dashboard.js
```

**Fix needed:**
- Verify `/api/feeds/test` endpoint in dashboard.py
- Check testFeed() function in dashboard.js
- Ensure proper error handling and user feedback

#### 3B. Delete Feed Button Not Working
**Symptom:** Clicking DEL does nothing or shows error  
**Expected:** Should delete feed after confirmation

**Check:**
```bash
# Does endpoint work?
curl -X DELETE http://localhost:8000/api/feeds \
  -H "Content-Type: application/json" \
  -d '{"url": "https://cointelegraph.com/rss"}'

# Check if feed is actually removed from rss_feeds.json
cat src/app/logs/rss_feeds.json | jq
```

#### 3C. Missing: Edit Feed Functionality
**Current:** Can only add or delete feeds  
**Needed:** Ability to edit feed name/URL without deleting

**Proposed UI:**
- EDIT button next to each feed
- Modal popup with pre-filled name/URL fields
- Save changes via PUT endpoint

#### 3D. Missing: Disable Feed (without deleting)
**Current:** Must delete to stop using a feed  
**Better:** Toggle active/inactive status

**Proposed implementation:**
```json
// rss_feeds.json structure
{
  "feeds": [
    {
      "name": "CoinTelegraph",
      "url": "https://cointelegraph.com/rss",
      "active": true,  // ← Add this field
      "status": "active",
      "last_fetch": "2025-10-15T12:00:00"
    }
  ]
}
```

**New UI elements needed:**
- Toggle switch or checkbox in feed list
- PUT endpoint: `/api/feeds/toggle`
- Filter feeds by `active: true` when fetching news

**Files to modify:**
- `src/app/dashboard.py` - Add edit/toggle endpoints
- `src/static/js/dashboard.js` - Add editFeed(), toggleFeed() functions
- `src/templates/dashboard.html` - Add EDIT button and toggle UI
- `src/app/news_fetcher.py` - Only fetch from active feeds

---

### 4. Trades vs Signals Clarity Needed
**Confusion:** What's the difference between a "trade" and a "signal"?  

**Current state:**
- `trades.json` - 468 entries (what are these?)
- `strategy_signals.jsonl` - Multiple entries (what are these?)
- Dashboard shows both "Recent Trades" and "Recent Signals"

**Need clear definitions:**

#### Terminology Clarification
```
SIGNAL = Strategy recommendation (BUY/SELL/HOLD)
├─ Generated by: StrategyManager
├─ Logged to: strategy_signals.jsonl
├─ Contains: All strategy inputs, reasoning, confidence
├─ Does NOT execute: Just a recommendation
└─ Example: "BUY BTC at $50k (confidence: 75%)"

TRADE = Actual position change (execution)
├─ Generated by: PaperTrader or LiveTrader
├─ Logged to: trades.json
├─ Contains: Execution details, fees, timestamp
├─ Affects balance: Yes
└─ Example: "Bought 0.001 BTC at $50k (fee: $0.13)"

ACTION = What was actually done
├─ Can be: BUY, SELL, or HOLD
├─ HOLD actions: Low confidence signals that don't meet threshold
├─ Logged to: trades.json (even HOLDs)
└─ Note: "HOLD" = signal generated but no execution
```

**Questions to answer:**
1. **Why 468 trades but only hold actions?**
   - Are these all HOLD decisions?
   - Check: `cat src/app/logs/trades.json | jq '[.[] | .action] | group_by(.) | map({action: .[0], count: length})'`

2. **What triggers an actual trade (not HOLD)?**
   - Minimum confidence threshold?
   - Risk manager approval?
   - Check `paper_trader.py` execution logic

3. **Should HOLDs be logged as "trades"?**
   - Maybe rename trades.json → actions.json?
   - Or separate files: trades.json (BUY/SELL only) + decisions.json (all actions)

**Proposed clarification for dashboard:**
```
OVERVIEW TAB:
├─ "Recent Signals" → Strategy recommendations (all symbols evaluated)
└─ "Recent Actions" → What bot actually did (including HOLDs)

TRADES TAB:
├─ Rename to "ACTIVITY" or "DECISIONS"
└─ Filter options:
    ├─ All actions (BUY/SELL/HOLD)
    ├─ Trades only (BUY/SELL)
    └─ By symbol

STRATEGIES TAB:
├─ Keep as "Strategy Signals"
└─ Show individual strategy outputs before aggregation
```

**Files to update:**
- Documentation explaining signal → trade flow
- Dashboard labels for clarity
- Consider splitting logs if needed

---

## 📋 PHASE 1.5 CHECKLIST

Before proceeding to Phase 2 (Backtesting), verify:

### System Status ✓
- [ ] LAST RUN shows actual timestamp
- [ ] NEXT RUN shows correct future time
- [ ] MESSAGE shows meaningful status
- [ ] Status updates every cycle

### Strategy Manager ✓
- [ ] Technical strategy is enabled and running
- [ ] Volume strategy is enabled and running
- [ ] Sentiment strategy is running
- [ ] strategy_signals.jsonl shows all 3 strategies
- [ ] Confidence scores make sense
- [ ] Final signal is proper weighted aggregation

### Feed Management ✓
- [ ] TEST button works (shows headline count)
- [ ] DELETE button works (removes feed)
- [ ] EDIT button implemented (modify name/URL)
- [ ] TOGGLE implemented (enable/disable without deleting)
- [ ] Feed status reflects actual state

### Data Clarity ✓
- [ ] Documentation explains signal vs trade vs action
- [ ] Dashboard labels are clear
- [ ] trades.json contains expected data
- [ ] Can filter by action type (BUY/SELL/HOLD)

---

## 🔍 DEBUGGING COMMANDS

### Check Strategy Manager
```bash
# View recent signals
tail -10 src/app/logs/strategy_signals.jsonl | jq

# Count strategies per signal
tail -50 src/app/logs/strategy_signals.jsonl | jq '.strategies | keys' | sort | uniq -c

# Should see ["sentiment", "technical", "volume"] for each
```

### Check Trades/Actions
```bash
# Count by action type
cat src/app/logs/trades.json | jq '[.[] | .action] | group_by(.) | map({action: .[0], count: length})'

# View recent actions
cat src/app/logs/trades.json | jq '.[-10:]'

# Check for actual BUY/SELL (not just HOLD)
cat src/app/logs/trades.json | jq '[.[] | select(.action != "hold")]'
```

### Check System Status
```bash
# Current status
cat src/app/logs/bot_status.json | jq

# API response
curl http://localhost:8000/status | jq

# Check when last cycle ran
cat src/app/logs/bot_status.json | jq '.last_status.time'
```

### Check Feed Management
```bash
# List feeds
curl http://localhost:8000/api/feeds | jq

# Test feed
curl -X POST http://localhost:8000/api/feeds/test \
  -H "Content-Type: application/json" \
  -d '{"url": "https://cointelegraph.com/rss"}' | jq

# Delete feed
curl -X DELETE http://localhost:8000/api/feeds \
  -H "Content-Type: application/json" \
  -d '{"url": "https://cointelegraph.com/rss"}' | jq
```

---

## 🎯 SUCCESS CRITERIA

Phase 1.5 complete when:
1. ✅ System status updates accurately every cycle
2. ✅ All 3 strategies evaluate every symbol
3. ✅ strategy_signals.jsonl shows multi-strategy consensus
4. ✅ Feed test/delete/edit/toggle all work
5. ✅ Clear understanding of signal → trade flow
6. ✅ Dashboard labels accurately reflect what data means

**Then and only then** → Proceed to Phase 2 (Backtesting)

---

## 📞 HANDOFF NOTE

**For next agent:** Don't start backtesting until these 4 issues are resolved. The backtesting engine will be useless if:
- Strategies aren't all running (garbage in = garbage out)
- System status is broken (can't trust cycle timing)
- Feed management is broken (sentiment strategy won't work)
- Data meaning is unclear (won't know what we're testing)

Fix Phase 1.5 first, THEN backtest. Quality over speed.

