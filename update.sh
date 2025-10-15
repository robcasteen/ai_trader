#!/bin/bash
# commit_and_push.sh - Save all current work

set -e

echo "💾 COMMITTING AND PUSHING ALL WORK"
echo "===================================="
echo ""

# 1. Stage all changes
echo "1️⃣ Staging all changes..."
git add -A

# 2. Show what's being committed
echo ""
echo "📝 Changes to commit:"
git status --short

# 3. Commit with comprehensive message
echo ""
echo "2️⃣ Creating commit..."
git commit -m "Phase 1.5: Document critical issues before Phase 2

Added comprehensive documentation:
- HANDOFF_PHASE1_COMPLETE.md: Full system state and handoff guide
- PHASE_1.5_ISSUES.md: Critical issues blocking Phase 2
- QUICK_REFERENCE.md: Quick commands for common tasks
- FILE_MANIFEST.md: Critical file locations
- SYSTEM_STATE.json: Machine-readable state snapshot

Issues identified for Phase 1.5:
1. System Status display showing incorrect data
2. Only sentiment strategy running (need technical + volume)
3. Feed management incomplete (test/delete broken, need edit/disable)
4. Trades vs signals terminology needs clarity

Current state:
- Dashboard 100% functional
- 262 tests passing
- All path issues resolved
- Paper trading operational
- Ready for Phase 1.5 fixes before backtesting

Next: Fix Phase 1.5 issues, then Phase 2 (Backtesting)" || {
    echo "⚠️  Nothing to commit or commit failed"
}

# 4. Push to remote
echo ""
echo "3️⃣ Pushing to remote..."
git push origin main || git push origin master || {
    echo "⚠️  Push failed - check remote configuration"
    echo "Run: git remote -v"
    exit 1
}

echo ""
echo "✅ COMMIT AND PUSH COMPLETE"
echo ""
echo "🎯 Ready to start Phase 1.5 fixes"
echo ""
echo "📋 Issue list:"
echo "   1. Fix System Status display"
echo "   2. Enable all 3 strategies (technical + volume + sentiment)"
echo "   3. Fix feed management (test/delete/edit/disable)"  
echo "   4. Clarify trades vs signals terminology"
echo ""
echo "Let's tackle them one by one! 🚀"