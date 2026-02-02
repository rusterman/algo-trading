#!/usr/bin/env python3
from config_loader import load_config

config = load_config('strategy_config.json')
dca_levels = sorted([abs(x) for x in config.dca_levels])

print("DCA Levels from config:", config.dca_levels)
print("DCA Levels (sorted absolute):", dca_levels)
print("\nExpected Drawdown Ranges for Excel Report:")

if dca_levels:
    print(f"  0% to -{dca_levels[0]}%")
    for i in range(len(dca_levels) - 1):
        print(f"  -{dca_levels[i]}% to -{dca_levels[i + 1]}%")
    print(f"  -{dca_levels[-1]}%+")
