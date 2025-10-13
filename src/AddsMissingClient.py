#!/usr/bin/env python3
"""
AI Trading Bot - Final Fix & Test Script
Adds missing Kraken client initialization and runs full system test
"""

import os
import sys
import json
from pathlib import Path

def fix_main_py():
    """Add missing KrakenClient initialization to main.py"""
    
    main_py_path = Path('src/app/main.py')
    
    if not main_py_path.exists():
        print(f"❌ Error: {main_py_path} not found!")
        return False
    
    print(f"📝 Reading {main_py_path}...")
    with open(main_py_path, 'r') as f:
        content = f.read()
    
    # Check if client is already initialized
    if 'client = KrakenClient()' in content:
        print("✅ KrakenClient already initialized!")
        return True
    
    # Check if import exists
    has_import = 'from app.client.kraken import KrakenClient' in content
    
    # Find the right place to add initialization
    lines = content.split('\n')
    
    # Find where other clients are initialized (paper_trader, notifier, etc.)
    insert_line = -1
    import_line = -1
    
    for idx, line in enumerate(lines):
        # Find import section
        if line.startswith('from app.') and import_line == -1:
            import_line = idx
        
        # Find initialization section (after imports, where paper_trader is created)
        if 'paper_trader' in line and '=' in line and insert_line == -1:
            insert_line = idx + 1
    
    # Add import if missing
    if not has_import and import_line != -1:
        print(f"➕ Adding import at line {import_line + 1}")
        lines.insert(import_line + 1, 'from app.client.kraken import KrakenClient')
        insert_line += 1  # Adjust for added line
    
    # Add client initialization
    if insert_line != -1:
        print(f"➕ Adding client initialization at line {insert_line + 1}")
        lines.insert(insert_line, 'client = KrakenClient()')
        lines.insert(insert_line + 1, '')  # Add blank line for readability
    else:
        print("⚠️  Could not find ideal insertion point. Adding after imports.")
        # Find last import
        last_import = 0
        for idx, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import = idx
        lines.insert(last_import + 2, 'client = KrakenClient()')
        lines.insert(last_import + 3, '')
    
    # Write back
    new_content = '\n'.join(lines)
    
    # Create backup
    backup_path = main_py_path.with_suffix('.py.backup')
    print(f"💾 Creating backup at {backup_path}")
    with open(backup_path, 'w') as f:
        f.write(content)
    
    # Write fixed version
    print(f"💾 Writing fixed version to {main_py_path}")
    with open(main_py_path, 'w') as f:
        f.write(new_content)
    
    print("✅ main.py has been fixed!")
    return True


def clear_seen_headlines():
    """Clear seen headlines to allow testing with fresh news"""
    
    seen_news_path = Path('src/logs/seen_news.json')
    
    if not seen_news_path.exists():
        print(f"ℹ️  {seen_news_path} doesn't exist yet, will be created on first run")
        return True
    
    print(f"🗑️  Clearing seen headlines in {seen_news_path}...")
    with open(seen_news_path, 'w') as f:
        json.dump({}, f)
    
    print("✅ Seen headlines cleared!")
    return True


def verify_files():
    """Verify all required files exist"""
    
    required_files = [
        'src/app/main.py',
        'src/app/client/kraken.py',
        'src/app/logic/sentiment.py',
        'src/app/news_fetcher.py',
        'src/app/strategies/strategy_manager.py',
        'src/app/dashboard.py',
        'templates/dashboard.html',
    ]
    
    print("🔍 Verifying required files...")
    all_exist = True
    
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - MISSING!")
            all_exist = False
    
    return all_exist


def run_validation():
    """Run the validation script"""
    
    print("\n" + "="*60)
    print("🧪 Running System Validation")
    print("="*60 + "\n")
    
    if not Path('validate_system.py').exists():
        print("⚠️  validate_system.py not found, skipping validation")
        return True
    
    import subprocess
    result = subprocess.run([sys.executable, 'validate_system.py'], 
                          capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    return result.returncode == 0


def show_next_steps():
    """Display next steps for the user"""
    
    print("\n" + "="*60)
    print("🎯 NEXT STEPS")
    print("="*60)
    print("""
1. Start the dashboard:
   python src/app/dashboard.py

2. Open browser to:
   http://localhost:5000

3. Click "Run Now" to trigger a trade cycle

4. Check the Strategies tab to see:
   - Real strategy names (not s1, s2, s3)
   - Actual prices from Kraken
   - Confidence scores and reasoning
   - Strategy-specific signals

5. Monitor logs:
   tail -f src/logs/strategy_signals.jsonl

6. Verify health monitor shows all green:
   - OpenAI API
   - Kraken API
   - RSS Feeds
   - Database

📊 Expected Strategy Output:
{
  "timestamp": "2025-10-12T14:30:00Z",
  "symbol": "XBTUSD",
  "price": 62450.00,
  "strategy": "technical_indicators",
  "signal": "buy",
  "confidence": 0.72,
  "reasoning": "RSI oversold + bullish MACD crossover"
}

🐛 Troubleshooting:
- If no signals appear: Check src/logs/seen_news.json is empty
- If prices are null: Check Kraken API in Health Monitor
- If strategies show as s1/s2/s3: Restart dashboard
- If sentiment fails: Check OpenAI API key in .env

📝 Commit Changes:
git add .
git commit -m "Fix: Add missing KrakenClient initialization"
git push origin main
""")


def main():
    """Main execution"""
    
    print("="*60)
    print("🤖 AI Trading Bot - Final Fix & Test")
    print("="*60 + "\n")
    
    # Step 1: Verify files
    if not verify_files():
        print("\n❌ Missing required files! Please check your project structure.")
        return 1
    
    # Step 2: Fix main.py
    if not fix_main_py():
        print("\n❌ Failed to fix main.py")
        return 1
    
    # Step 3: Clear seen headlines
    if not clear_seen_headlines():
        print("\n❌ Failed to clear seen headlines")
        return 1
    
    # Step 4: Run validation
    validation_passed = run_validation()
    
    # Step 5: Show next steps
    show_next_steps()
    
    if validation_passed:
        print("\n✅ ALL SYSTEMS GO! Bot is ready to trade! 🚀")
        return 0
    else:
        print("\n⚠️  Some validation checks failed. Review output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())