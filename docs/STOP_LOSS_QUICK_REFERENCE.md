# Stop-Loss Implementation: Quick Reference

## Overview

This document serves as a quick lookup for the stop-loss implementation design.

---

## Key Files & Changes

| File | Changes | Priority |
|------|---------|----------|
| `strategy_config.json` | Add `stop_loss_percent` parameter | ✓ First |
| `config_loader.py` | Add validation for stop_loss_percent | ✓ First |
| `dca_strategy.py` | Add all core logic | ✓ Main |
| `run_backtest.py` | Pass stop_loss_percent to strategy | ✓ Second |

---

## Core Concepts

### Stop-Loss Trigger
```
threshold = anchor_price × (1 - stop_loss_percent/100)
If candle.low ≤ threshold → Stop-loss triggered
```

### Loss Calculation
```
loss_pct = (exit_price - anchor_price) / anchor_price × 100
capital_loss = abs(loss_pct/100) × total_invested
available_budget -= capital_loss
```

### Execution Order (Per Candle)
1. **Check DCA fills** (candle.low ≤ entry_price)
2. **Check Stop-Loss** (candle.low ≤ threshold) ← NEW
3. **Check Take-Profit** (candle.high ≥ tp_price)

---

## Methods to Implement

### In DCAStrategy class:

```python
# Calculation
calculate_stop_loss_threshold() → Optional[float]

# Detection
check_stop_loss_hit(candle_low: float) → bool

# Execution
close_trade_with_loss(exit_time, loss_price, available_budget) 
  → (Trade, float)

# Statistics
calculate_backtest_results() → BacktestResults
```

---

## Data Structures to Modify

### Trade dataclass - Add fields:
```python
stop_loss_triggered: bool = False
stop_loss_price: Optional[float] = None
stop_loss_loss: float = 0.0
completion_reason: str = "take_profit"  # or "stop_loss"
```

### New - BacktestResults dataclass:
```python
@dataclass
class BacktestResults:
    initial_budget: float
    final_budget: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    stopped_out_trades: int
    total_profit: float
    total_loss: float
    net_pnl: float
    total_roi: float
    win_rate: float
    stop_loss_rate: float
    # ... more metrics
```

---

## Configuration

### In strategy_config.json:
```json
{
  "stop_loss_percent": 10.0,
  ...rest of config...
}
```

### Validation Rules:
- `stop_loss_percent >= 0` (must be non-negative)
- `stop_loss_percent == 0` → Disabled (backward compatible)
- Warn if `stop_loss_percent > 50%` (too aggressive)

---

## Behavioral Rules

### When Disabled (stop_loss_percent = 0):
- `calculate_stop_loss_threshold()` returns `None`
- `check_stop_loss_hit()` always returns `False`
- Stop-loss logic skipped entirely
- Identical behavior to pre-SL system ✓ **Backward compatible**

### When Enabled (stop_loss_percent > 0):
- Stop-loss check executes every candle in trade
- If threshold breached → immediate position close
- Loss deducted from available_budget
- Affects all future trades

---

## Execution Flow (Modified)

```
run_backtest(df):
  available_budget = initial_budget  ← NEW
  
  for each candle:
    if NOT in_trade:
      → Check for entry trigger
    
    if IN_TRADE:
      → Check DCA fills
      → ★ Check STOP-LOSS (NEW)
         if SL hit:
           → close_trade_with_loss()
           → available_budget -= loss  ← KEY
           → reset & continue
      → Check TP (only if no SL)
         if TP hit:
           → close_trade()
           → available_budget += profit ← UPDATE
           → reset & continue
```

---

## Statistics Calculated

### Trade Counts:
- `total_trades` - All completed trades
- `winning_trades` - Trades with profit > 0
- `losing_trades` - Trades with profit < 0
- `stopped_out_trades` - Trades closed by SL ← NEW

### Profit/Loss:
- `total_profit` - Sum of all gains
- `total_loss` - Sum of all losses (absolute value)
- `net_pnl` - Total profit/loss
- `total_roi` = (final_budget - initial_budget) / initial_budget × 100

### Rates:
- `win_rate` = winning_trades / total_trades × 100
- `stop_loss_rate` = stopped_out_trades / total_trades × 100 ← NEW

### Averages:
- `avg_trade_pnl` - Average P&L per trade
- `avg_profit_magnitude` - Average win size
- `avg_loss_magnitude` - Average loss size

---

## Edge Cases Handled

| Case | Handling |
|------|----------|
| SL Disabled | Returns None/False, logic skipped |
| SL + TP same candle | SL executes first (pessimistic) |
| Multiple DCA fills before SL | All positions liquidated at SL price |
| Entry + SL same candle | SL still applies to new position |
| No fills before SL | SL not triggered (no position) |
| Fractional losses | Round to nearest cent (ROUND_HALF_UP) |

---

## Testing Checklist

- [ ] `stop_loss_percent = 0` produces identical results to original
- [ ] `stop_loss_percent > 0` triggers stop-loss correctly
- [ ] Loss deducted from available_budget immediately
- [ ] Budget accounting is consistent (final = initial + all P&L)
- [ ] Multiple trades all account properly
- [ ] SL executes before TP when both triggered
- [ ] Backtest is deterministic (same input = same output)

---

## Common Pitfalls to Avoid

### ❌ Wrong: Using entry_price (from DCA fill)
```python
# DON'T DO THIS:
loss_threshold = last_dca_level.fill_price * 0.9
# This is inconsistent with TP calculation
```

### ✓ Correct: Using anchor_price
```python
# DO THIS:
loss_threshold = self.anchor_price * (1 - stop_loss_percent/100)
# Consistent with TP which uses avg_price = A/Q
```

### ❌ Wrong: Not updating available_budget
```python
# DON'T DO THIS:
trade = close_trade_with_loss(...)
# Forget to update available_budget
# Next trade uses old budget
```

### ✓ Correct: Update immediately
```python
# DO THIS:
trade, available_budget = close_trade_with_loss(..., available_budget)
self.available_budget = available_budget  # Update tracking
# Or pass as self.available_budget in method
```

### ❌ Wrong: Checking SL after TP
```python
# DON'T DO THIS:
if check_take_profit_hit(candle_high):
    close_trade()  # Close for profit
if check_stop_loss_hit(candle_low):  # Too late!
    # Already closed above
```

### ✓ Correct: Check SL before TP
```python
# DO THIS:
if check_stop_loss_hit(candle_low):
    close_trade_with_loss()
elif check_take_profit_hit(candle_high):  # Only if no SL
    close_trade()
```

---

## Performance Considerations

- Stop-loss check is O(1) - simple threshold comparison
- No additional data structures needed
- Minimal memory overhead
- Backtest performance unchanged

---

## Output Format Example

```
BACKTEST RESULTS - DCA STRATEGY
======================================================================
Initial Budget:     $8,000.00
Final Budget:       $8,450.00
Total P&L:          +$450.00
ROI:                +5.63%

Trade Summary:
─────────────────────────────────────────────────────────────────────
Total Trades:       12
  Winning:          9 (75.0%)
  Losing:           3 (25.0%)
  Stopped Out:      2 (16.7%)  ← NEW

Profit & Loss:
─────────────────────────────────────────────────────────────────────
Total Profit:       $820.00
Total Loss:         -$370.00
Avg Trade P&L:      +$37.50

Stop-Loss (Enabled):
─────────────────────────────────────────────────────────────────────
Stop-Loss %:        10.0
Stopped Out:        2 trades
Total SL Loss:      -$240.00  ← NEW
```

---

## Debugging Commands

```bash
# Check stop-loss calculation
python -c "
from dca_strategy import DCAStrategy
s = DCAStrategy(stop_loss_percent=10)
s.anchor_price = 100
print(s.calculate_stop_loss_threshold())  # Should print 90.0
"

# Run backtest with stop-loss
python run_backtest.py

# Check config loads correctly
python -c "
from config_loader import load_config
c = load_config('strategy_config.json')
print(f'Stop-Loss: {c.stop_loss_percent}%')
"
```

---

## Implementation Order (Recommended)

1. **Update configuration** 
   - Add to JSON, config_loader.py
   - Test config loads correctly

2. **Update data structures**
   - Add fields to Trade dataclass
   - Create BacktestResults dataclass

3. **Add core methods**
   - `calculate_stop_loss_threshold()`
   - `check_stop_loss_hit()`
   - `close_trade_with_loss()`

4. **Modify backtest loop**
   - Add available_budget tracking
   - Insert SL check between DCA and TP
   - Update budget on trade close

5. **Add statistics**
   - `calculate_backtest_results()`
   - Update print output

6. **Test thoroughly**
   - Backward compatibility
   - SL triggering
   - Budget accounting
   - Edge cases

---

## Financial Correctness Guarantees

✓ No phantom capital  
✓ Deterministic outcomes  
✓ Consistent ROI calculation  
✓ Proper loss tracking  
✓ Budget conservation  
✓ All capital accounted for  

---

## Reference Documents

- **STOP_LOSS_DESIGN.md** - Comprehensive design document
- **STOP_LOSS_IMPLEMENTATION.md** - Code change details
- **STOP_LOSS_EXAMPLES.md** - Walkthroughs and edge cases
- **ALGORITHM_SPECIFICATION.md** - Core algorithm (existing)
