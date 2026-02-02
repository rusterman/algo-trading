#!/usr/bin/env python3
"""
Detailed check of drawdown distribution
"""
from config_loader import load_config
from dca_strategy import DCAStrategy, load_and_prepare_data
import pandas as pd

config = load_config('strategy_config.json')
df = load_and_prepare_data(config.csv_file)
if config.start_date:
    start = pd.to_datetime(config.start_date)
    df = df[df['datetime'] >= start]
if config.end_date:
    end = pd.to_datetime(config.end_date)
    df = df[df['datetime'] <= end]

strategy = DCAStrategy(
    initial_budget=config.initial_budget,
    budget_per_level=config.budget_allocation,
    dca_levels=config.dca_levels,
    take_profit_percent=config.take_profit_percent,
    stop_loss_percent=config.stop_loss_percent
)

trades = strategy.run_backtest(df)

# Collect all drawdowns
drawdowns = []
for trade in trades:
    dd = abs((trade.deepest_price - trade.anchor_price) / trade.anchor_price) * 100
    drawdowns.append(dd)

drawdowns.sort()

print(f"Drawdown Distribution (all {len(drawdowns)} trades):")
print(f"  Min: {min(drawdowns):.2f}%")
print(f"  Max: {max(drawdowns):.2f}%")
print(f"  Median: {sorted(drawdowns)[len(drawdowns)//2]:.2f}%")
print(f"  Mean: {sum(drawdowns)/len(drawdowns):.2f}%")

print(f"\nBreakdown by range:")
print(f"  < 6%:      {sum(1 for d in drawdowns if d < 6)}")
print(f"  6% - 9%:   {sum(1 for d in drawdowns if 6 <= d < 9)}")
print(f"  6% - 9% (<=): {sum(1 for d in drawdowns if 6 <= d <= 9)}")
print(f"  9% - 12%:  {sum(1 for d in drawdowns if 9 <= d < 12)}")
print(f"  12%+:      {sum(1 for d in drawdowns if d >= 12)}")

print(f"\nSample values at boundaries:")
in_6_to_9 = [d for d in drawdowns if 6 <= d <= 9]
print(f"  In 6% to 9% range: {in_6_to_9[:10]}")
