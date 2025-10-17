cd /home/rcasteen/kraken-ai-bot
PYTHONPATH=src python3 << 'PYEOF'
import inspect
from app.strategies.strategy_manager import StrategyManager

# Get the source code of the method
source = inspect.getsource(StrategyManager._weighted_vote_aggregation)

# Check if our fix is in there
if 'if signal in ["BUY", "SELL"] and actionable_weight > 0:' in source:
    print("✅ Fix IS in the imported code")
else:
    print("❌ Fix NOT in the imported code")
    print("\nActual code:")
    print(source)
PYEOF