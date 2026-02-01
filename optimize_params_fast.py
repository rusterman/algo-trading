"""
Fast Parameter optimization for DCA Strategy
"""
import pandas as pd
from dca_strategy import DCAStrategy, load_and_prepare_data
from config_loader import load_config
import json
import sys

def test_configuration(df, levels, allocations, tp_percent):
    """Test a single configuration"""
    try:
        if len(levels) != len(allocations):
            return None
        
        strategy = DCAStrategy(
            initial_budget=100000,
            budget_per_level=allocations,
            dca_levels=levels,
            take_profit_percent=tp_percent
        )
        
        trades = strategy.run_backtest(df)
        
        if not trades:
            return None
        
        total_pnl = sum(t.profit_loss for t in trades)
        roi = (total_pnl / strategy.initial_budget) * 100
        
        return {
            'roi': roi,
            'pnl': total_pnl,
            'trades': len(trades),
            'levels': levels,
            'allocations': allocations,
            'tp': tp_percent,
        }
    except Exception as e:
        return None


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

print(f"Backtest data: {len(df)} candles")
print(f"Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}\n")

# Get baseline
baseline_strategy = DCAStrategy(
    initial_budget=config.initial_budget,
    budget_per_level=config.dca_allocations,
    dca_levels=config.dca_levels,
    take_profit_percent=config.take_profit_percent,
)
baseline_trades = baseline_strategy.run_backtest(df)
baseline_roi = (sum(t.profit_loss for t in baseline_trades) / baseline_strategy.initial_budget) * 100

print(f"Current Configuration:")
print(f"  Levels: {config.dca_levels}")
print(f"  Allocations: {config.dca_allocations}")
print(f"  Take Profit: {config.take_profit_percent}%")
print(f"  ROI: {baseline_roi:.2f}% ({len(baseline_trades)} trades)\n")

# Compact parameter space
level_sets = [
    [-3, -6, -10, -13, -16, -20],
    [-3, -6, -10, -13, -16, -20, -25],
    [-3, -6, -10, -13, -16, -20, -25, -30],
    [-2, -4, -8, -12, -16, -20],
    [-3, -6, -9, -12, -16, -20],
]

allocation_sets = [
    [1000, 2000, 4000, 8000, 16000, 32000],
    [1000, 2000, 4000, 8000, 16000, 32000, 64000],
    [1000, 2000, 4000, 8000, 16000, 32000, 64000, 128000],
    [2000, 4000, 8000, 16000, 32000, 64000],
]

tp_values = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

print(f"Testing {len(level_sets)} level sets × {len(allocation_sets)} allocation sets × {len(tp_values)} TP values = {len(level_sets) * len(allocation_sets) * len(tp_values)} configurations...\n")

best_results = []
config_count = 0

for levels in level_sets:
    for alloc in allocation_sets:
        if len(levels) != len(alloc):
            continue
        
        for tp in tp_values:
            config_count += 1
            
            result = test_configuration(df, levels, alloc, tp)
            
            if result:
                best_results.append(result)
                
                if config_count % 25 == 0:
                    best_roi = max(r['roi'] for r in best_results) if best_results else 0
                    print(f"Tested {config_count} configs... Best ROI: {best_roi:.2f}%")

if not best_results:
    print("No valid configurations found!")
    sys.exit(1)

# Sort by ROI
best_results.sort(key=lambda x: x['roi'], reverse=True)

print(f"\n{'='*80}")
print(f"TOP 15 CONFIGURATIONS (by ROI)")
print(f"{'='*80}\n")

for i, result in enumerate(best_results[:15], 1):
    print(f"{i}. ROI: {result['roi']:>8.2f}% | P&L: ${result['pnl']:>10,.0f} | Trades: {result['trades']:>3d}")
    print(f"   Levels: {result['levels']}")
    print(f"   Allocations: {result['allocations']}")
    print(f"   Take Profit: {result['tp']}%\n")

# Get best
best = best_results[0]

# Compare with baseline
improvement = ((best['roi'] - baseline_roi) / baseline_roi) * 100

print(f"{'='*80}")
print(f"BEST CONFIGURATION")
print(f"{'='*80}")
print(f"\nROI: {best['roi']:.2f}%")
print(f"P&L: ${best['pnl']:,.2f}")
print(f"Total Trades: {best['trades']}")
print(f"\nConfiguration:")
print(f"  dca_levels: {best['levels']}")
print(f"  dca_allocations: {best['allocations']}")
print(f"  take_profit_percent: {best['tp']}")

print(f"\nBaseline ROI: {baseline_roi:.2f}%")
print(f"Best ROI: {best['roi']:.2f}%")
print(f"Improvement: {improvement:+.2f}%")

# Save optimized config
optimized_config = {
    "csv_file": config.csv_file,
    "start_date": config.start_date,
    "end_date": config.end_date,
    "initial_budget": config.initial_budget,
    "dca_levels": best['levels'],
    "dca_allocations": best['allocations'],
    "take_profit_percent": best['tp']
}

with open('strategy_config_optimized.json', 'w') as f:
    json.dump(optimized_config, f, indent=2)

print(f"\n✓ Optimized configuration saved to 'strategy_config_optimized.json'")
