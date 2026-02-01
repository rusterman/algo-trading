"""
Parameter optimization for DCA Strategy
Finds the best combination of dca_levels, dca_allocations, and take_profit_percent
"""
import pandas as pd
from dca_strategy import DCAStrategy, load_and_prepare_data
from config_loader import load_config
import json

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
            'deepest_level_count': max([t.deepest_level for t in trades]) if trades else 0
        }
    except Exception as e:
        print(f"Error testing config: {e}")
        return None


# Load data
print("Loading data...")
df = load_and_prepare_data("data/sol_15m_data_2020_to_2025.csv")

# Filter by date range
start = pd.to_datetime("2025-01-01")
end = pd.to_datetime("2026-01-01")
df = df[df['datetime'] >= start]
df = df[df['datetime'] <= end]

print(f"Backtest data: {len(df)} candles")
print(f"Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}\n")

# Define parameter space
level_sets = [
    [-3, -6, -10, -13, -16, -20],           # Baseline (user's request)
    [-3, -6, -10, -13, -16, -20, -25],      # Add level 7
    [-2, -4, -8, -12, -16, -20],            # Tighter spacing
    [-3, -6, -9, -12, -16, -20],            # Mixed spacing
    [-4, -8, -12, -16, -20, -24],           # Wider spacing
    [-5, -10, -15, -20, -25, -30],          # Much wider
    [-2, -5, -8, -12, -16, -20],            # Asymmetric
    [-3, -6, -10, -13, -16, -20, -25, -30], # 8 levels
    [-3, -5, -8, -11, -15, -20],            # Finer spacing
]

allocation_sets = [
    [1000, 2000, 4000, 8000, 16000, 32000],      # Baseline (user's request)
    [1000, 2000, 4000, 8000, 16000, 32000, 64000], # Add level 7
    [1000, 2000, 4000, 8000, 16000, 32000, 64000, 128000], # 8 levels
    [2000, 4000, 8000, 16000, 32000, 64000],    # Double amounts
    [1000, 1500, 3000, 6000, 12000, 24000],     # Lower allocations
    [1500, 3000, 6000, 12000, 24000, 48000],    # Mid allocations
    [100000/6]*6,                                  # Equal split
    [100000/7]*7,                                  # Equal split (7 levels)
]

tp_values = [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 9.0, 10.0]

# Run optimization
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
                
                if config_count % 50 == 0:
                    print(f"Tested {config_count} configs... Best ROI so far: {max(r['roi'] for r in best_results):.2f}%")

# Sort by ROI
best_results.sort(key=lambda x: x['roi'], reverse=True)

print(f"\n{'='*80}")
print(f"TOP 20 CONFIGURATIONS (by ROI)")
print(f"{'='*80}\n")

for i, result in enumerate(best_results[:20], 1):
    print(f"{i}. ROI: {result['roi']:>8.2f}% | P&L: ${result['pnl']:>12,.0f} | Trades: {result['trades']:>4d}")
    print(f"   Levels: {result['levels']}")
    print(f"   Allocations: {result['allocations']}")
    print(f"   Take Profit: {result['tp']}%")
    print()

# Save best configuration
best = best_results[0]
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

# Compare with baseline
baseline_roi = 425.60
improvement = ((best['roi'] - baseline_roi) / baseline_roi) * 100

print(f"\nBaseline ROI: {baseline_roi:.2f}%")
print(f"Best ROI: {best['roi']:.2f}%")
print(f"Improvement: {improvement:+.2f}%")

# Create optimized config
optimized_config = {
    "csv_file": "data/sol_15m_data_2020_to_2025.csv",
    "start_date": "2020-01-01",
    "end_date": "2026-01-01",
    "initial_budget": 100000,
    "dca_levels": best['levels'],
    "dca_allocations": best['allocations'],
    "take_profit_percent": best['tp']
}

# Save to file
with open('strategy_config_optimized.json', 'w') as f:
    json.dump(optimized_config, f, indent=2)

print(f"\n✓ Optimized configuration saved to 'strategy_config_optimized.json'")
