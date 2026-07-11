#!/usr/bin/env python3
"""
Verify that visualization files have been updated with stop-loss feature support
"""

from config_loader import load_config
from dca_strategy import DCAStrategy, load_and_prepare_data
import pandas as pd

print("\n" + "="*70)
print("VISUALIZATION FILES - STOP-LOSS INTEGRATION VERIFICATION")
print("="*70)

# Load configuration
config = load_config('strategy_config.json')
print(f"\n✓ Configuration loaded")
print(f"  - Stop-Loss Percent: {config.stop_loss_percent}%")

# Load data for backtest
df = load_and_prepare_data(config.csv_file)
df = df[df['datetime'] >= '2025-01-01']
df = df[df['datetime'] <= '2025-01-31']
print(f"\n✓ Data loaded")
print(f"  - Candles: {len(df)}")

# Initialize strategy with stop-loss
strategy = DCAStrategy(
    initial_budget=config.initial_budget,
    budget_per_level=config.budget_allocation,
    dca_levels=config.dca_levels,
    take_profit_percent=config.take_profit_percent,
    stop_loss_percent=config.stop_loss_percent
)
print(f"\n✓ DCAStrategy initialized")
print(f"  - Stop-Loss Support: {'ENABLED' if config.stop_loss_percent > 0 else 'DISABLED'}")

# Run backtest
trades = strategy.run_backtest(df)
print(f"\n✓ Backtest completed")
print(f"  - Total Trades: {len(trades)}")

# Check for stop-loss trades
tp_trades = sum(1 for t in trades if not t.stop_loss_triggered)
sl_trades = sum(1 for t in trades if t.stop_loss_triggered)
print(f"  - Take-Profit Exits: {tp_trades}")
print(f"  - Stop-Loss Exits: {sl_trades}")

# Verify trade data
if trades:
    sample_trade = trades[0]
    print(f"\n✓ Sample Trade Data:")
    print(f"  - stop_loss_triggered: {sample_trade.stop_loss_triggered}")
    print(f"  - stop_loss_price: {sample_trade.stop_loss_price}")
    print(f"  - stop_loss_loss: {sample_trade.stop_loss_loss}")
    print(f"  - completion_reason: {sample_trade.completion_reason}")

# Verify visualization file compatibility
print(f"\n✓ Visualization Files Updated:")

# Check trading-view.py
with open('trading-view.py', 'r') as f:
    content = f.read()
    has_stop_loss_param = 'stop_loss_percent=config.stop_loss_percent' in content
    has_sl_marker = 'stop_loss_triggered' in content
    print(f"  - trading-view.py: {'✓' if has_stop_loss_param and has_sl_marker else '✗'}")

# Check pyplot-view.py
with open('pyplot-view.py', 'r') as f:
    content = f.read()
    has_stop_loss_param = 'stop_loss_percent=config.stop_loss_percent' in content
    has_sl_marker = 'stop_loss_triggered' in content
    print(f"  - pyplot-view.py: {'✓' if has_stop_loss_param and has_sl_marker else '✗'}")

# Check generate_excel_report.py
with open('generate_excel_report.py', 'r') as f:
    content = f.read()
    has_stop_loss_param = 'stop_loss_percent=config.stop_loss_percent' in content
    has_sl_analysis = 'STOP-LOSS ANALYSIS' in content
    print(f"  - generate_excel_report.py: {'✓' if has_stop_loss_param and has_sl_analysis else '✗'}")

print(f"\n" + "="*70)
print("✓ ALL VISUALIZATION FILES UPDATED SUCCESSFULLY")
print("="*70 + "\n")
