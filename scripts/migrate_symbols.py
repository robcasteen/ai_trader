"""
Migrate existing trades.json and holdings.json to use canonical symbols.
"""
import json
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.utils.symbol_normalizer import normalize_symbol

LOGS_DIR = Path(__file__).parent.parent / 'src' / 'app' / 'logs'

def migrate_trades():
    """Normalize all symbols in trades.json"""
    trades_file = LOGS_DIR / 'trades.json'
    
    if not trades_file.exists():
        print("No trades.json found")
        return
    
    with open(trades_file, 'r') as f:
        trades = json.load(f)
    
    normalized_count = 0
    for trade in trades:
        old_symbol = trade['symbol']
        try:
            new_symbol = normalize_symbol(old_symbol)
            if old_symbol != new_symbol:
                trade['symbol'] = new_symbol
                normalized_count += 1
        except ValueError:
            print(f"Warning: Unknown symbol '{old_symbol}' in trade, skipping")
    
    # Backup original
    backup_file = LOGS_DIR / 'trades.json.before_migration'
    with open(backup_file, 'w') as f:
        json.dump(trades, f, indent=2)
    
    # Write normalized
    with open(trades_file, 'w') as f:
        json.dump(trades, f, indent=2)
    
    print(f"✅ Migrated {normalized_count} trades")
    print(f"📁 Backup saved to: {backup_file}")

def rebuild_holdings():
    """Rebuild holdings.json from normalized trades"""
    trades_file = LOGS_DIR / 'trades.json'
    holdings_file = LOGS_DIR / 'holdings.json'
    
    if not trades_file.exists():
        print("No trades.json found")
        return
    
    with open(trades_file, 'r') as f:
        trades = json.load(f)
    
    holdings = {}
    
    for trade in trades:
        symbol = trade['symbol']
        action = trade['action'].upper()
        amount = trade['amount']
        price = trade['price']
        
        if action == 'BUY':
            if symbol in holdings:
                old_amount = holdings[symbol]['amount']
                old_avg = holdings[symbol]['avg_price']
                new_amount = old_amount + amount
                new_avg = ((old_amount * old_avg) + (amount * price)) / new_amount
                holdings[symbol] = {
                    'amount': new_amount,
                    'avg_price': new_avg,
                    'current_price': price
                }
            else:
                holdings[symbol] = {
                    'amount': amount,
                    'avg_price': price,
                    'current_price': price
                }
        
        elif action == 'SELL':
            if symbol in holdings:
                holdings[symbol]['amount'] -= amount
                holdings[symbol]['current_price'] = price
                
                if holdings[symbol]['amount'] <= 0.0001:
                    del holdings[symbol]
    
    # Calculate market values and P&L
    for symbol, pos in holdings.items():
        pos['market_value'] = pos['amount'] * pos['current_price']
        pos['cost_basis'] = pos['amount'] * pos['avg_price']
        pos['unrealized_pnl'] = pos['market_value'] - pos['cost_basis']
    
    # Backup original
    if holdings_file.exists():
        backup_file = LOGS_DIR / 'holdings.json.before_migration'
        with open(holdings_file, 'r') as f:
            old_holdings = json.load(f)
        with open(backup_file, 'w') as f:
            json.dump(old_holdings, f, indent=2)
        print(f"📁 Holdings backup saved to: {backup_file}")
    
    # Write new holdings
    with open(holdings_file, 'w') as f:
        json.dump(holdings, f, indent=2)
    
    print(f"✅ Rebuilt holdings with {len(holdings)} positions")
    for symbol, pos in holdings.items():
        print(f"   {symbol}: {pos['amount']:.8f} @ ${pos['avg_price']:.2f}")

if __name__ == '__main__':
    print("🔄 Starting symbol migration...\n")
    migrate_trades()
    print()
    rebuild_holdings()
    print("\n✅ Migration complete!")
