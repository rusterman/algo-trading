import pandas as pd
from dca_strategy import DCAStrategy, load_and_prepare_data
from config_loader import load_config

# Load data
print("Loading data...")
config = load_config("strategy_config.json")
df = load_and_prepare_data(config.csv_file)

# Filter by date range
if config.start_date:
    start = pd.to_datetime(config.start_date)
    df = df[df['datetime'] >= start]
if config.end_date:
    end = pd.to_datetime(config.end_date)
    df = df[df['datetime'] <= end]

print(f"Backtest data: {len(df)} candles\n")

# Test variations around the best config (triple allocations at 5.0% TP)
best_configs = [
    ([-3, -6, -10, -13, -16, -20, -25, -30], [3000, 6000, 12000, 24000, 48000, 96000, 192000, 384000], 4.0),
    ([-3, -6, -10, -13, -16, -20, -25, -30], [3000, 6000, 12000, 24000, 48000, 96000, 192000, 384000], 4.5),
    ([-3, -6, -10, -13, -16, -20, -25, -30], [3000, 6000, 12000, 24000, 48000, 96000, 192000, 384000], 5.0),
    ([-3, -6, -10, -13, -16, -20, -25, -30], [3000, 6000, 12000, 24000, 48000, 96000, 192000, 384000], 5.5),
    ([-3, -6, -10, -13, -16, -20, -25, -30], [3000, 6000, 12000, 24000, 48000, 96000, 192000, 384000], 6.0),
    # Try quadruple allocations
    ([-3, -6, -10, -13, -16, -20, -25, -30], [4000, 8000, 16000, 32000, 64000, 128000, 256000, 512000], 5.0),
    # Try different level spacing with triple alloc
    ([-4, -8, -12, -16, -20, -24, -28, -32], [3000, 6000, 12000, 24000, 48000, 96000, 192000, 384000], 5.0),
    ([-2, -4, -8, -12, -16, -20, -24, -28], [3000, 6000, 12000, 24000, 48000, 96000, 192000, 384000], 5.0),
]

results = []

for i, (levels, allocs, tp) in enumerate(best_configs, 1):
    print(f"{i}. Testing: TP={tp}%, Levels={len(levels)}, Alloc={allocs[-1]}")
    
    strategy = DCAStrategy(
        initial_budget=config.initial_budget,
        budget_per_level=allocs,
        dca_levels=levels,
        take_profit_percent=tp
    )
    
    trades = strategy.run_backtest(df)
    roi = (sum(t.profit_loss for t in trades) / strategy.initial_budget) * 100
    pnl = sum(t.profit_loss for t in trades)
    
    print(f"   ✓ ROI: {roi:.2f}% | P&L: ${pnl:,.0f} | Trades: {len(trades)}\n")
    
    results.append({
        'roi': roi,
        'pnl': pnl,
        'trades': len(trades),
        'levels': levels,
        'allocations': allocs,
        'tp': tp
    })

# Sort by ROI
results.sort(key=lambda x: x['roi'], reverse=True)

print("="*80)
print("TOP CONFIGURATIONS")
print("="*80 + "\n")

for i, r in enumerate(results, 1):
    print(f"{i}. ROI: {r['roi']:>7.2f}% | P&L: ${r['pnl']:>10,.0f} | Trades: {r['trades']:>3d} | TP: {r['tp']}%")
