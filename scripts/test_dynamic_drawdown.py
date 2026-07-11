#!/usr/bin/env python3
"""
Test the dynamic drawdown analysis with actual config
"""
from config_loader import load_config
from dca_strategy import DCAStrategy, load_and_prepare_data
from generate_excel_report import ExcelReportGenerator
import pandas as pd

config = load_config('strategy_config.json')
print(f"Configuration:")
print(f"  DCA Levels: {config.dca_levels}")
print(f"  DCA Levels (sorted absolute): {sorted([abs(x) for x in config.dca_levels])}")

# Load and run backtest
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
print(f"\nBacktest Results:")
print(f"  Total Trades: {len(trades)}")

# Create report generator and test drawdown analysis
generator = ExcelReportGenerator(config, strategy, trades)
analysis = generator._calculate_drawdown_analysis()

print(f"\nGenerated Drawdown Ranges:")
for range_label in sorted(analysis.keys(), 
                          key=lambda x: float(x.split('%')[0].lstrip('-')) if x[0] == '-' else float(x.split('%')[0])):
    data = analysis[range_label]
    print(f"  {range_label}: {data['count']} trades, max drawdown {data['max_dd']:.2f}%")

# Check some actual drawdowns
print(f"\nSample Trade Drawdowns:")
for i, trade in enumerate(trades[:10]):
    dd = abs((trade.deepest_price - trade.anchor_price) / trade.anchor_price) * 100
    print(f"  Trade {i+1}: {dd:.2f}%")
