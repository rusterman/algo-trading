# Stop-Loss Examples & Edge Cases

## Visual Walkthrough Examples

### Example 1: Simple Stop-Loss Trigger

```
CONFIG:
  initial_budget = $1,000
  stop_loss_percent = 10%
  dca_allocations = [250, 500, 250]
  dca_levels = [-5%, -10%, -15%]
  take_profit_percent = 5%

TIMELINE:

Candle 1 (Start):
  anchor_price = $100
  
Candle 5 (Entry):
  candle.low = $95 (within -5% DCA-1)
  → ENTRY TRIGGERED
  → Fill DCA-1 @ $95
  → Position: 250/95 = 2.63 coins @ avg $95
  
  RISK CALCULATION:
  - entry_price = $100 (anchor)
  - stop_loss_threshold = $100 × (1 - 0.10) = $90
  - If price touches $90 or lower → STOP-LOSS

Candle 8:
  candle.low = $88 (breaches $90 threshold)
  → STOP-LOSS HIT ✗
  → Exit price = $90 (threshold)
  → Loss % = ($90 - $100) / $100 = -10%
  → Coins held = 2.63 (from DCA-1 only)
  → Total return = 2.63 × $90 = $236.70
  → Capital loss = $250 × 10% = $25
  → Trade result: -$25 (-10%)
  
  BUDGET UPDATE:
  - available_budget = $1,000 - $25 = $975
  
Candle 15 (New Cycle):
  available_budget = $975 (reduced!)
  new anchor = candle.high
  → Next trade uses $975 budget, not $1,000
  → This affects DCA allocations in future trades
```

**Key Insight**: Loss immediately reduces available capital for subsequent trades.

---

### Example 2: Multiple DCA Fills Before Stop-Loss

```
CONFIG:
  initial_budget = $1,000
  stop_loss_percent = 15%
  dca_allocations = [200, 300, 500]
  dca_levels = [-5%, -10%, -20%]

TIMELINE:

Candle 1: anchor = $100

Candle 5: candle.low = $95 (touches -5%)
  → Fill DCA-1 @ $95
  → Invested: $200 @ $95 = 2.11 coins
  → Stop threshold = $100 × 0.85 = $85

Candle 10: candle.low = $90 (touches -10%)
  → Fill DCA-2 @ $90
  → Invested: $300 @ $90 = 3.33 coins
  → Total invested: $500
  → Total coins: 2.11 + 3.33 = 5.44 coins
  → Avg price: $500 / 5.44 = $91.91
  → Stop threshold still = $85 (based on anchor)

Candle 15: candle.low = $84 (breaches $85)
  → STOP-LOSS HIT ✗
  → Exit price = $85
  → Total return = 5.44 × $85 = $462.40
  → Loss % = ($85 - $100) / $100 = -15%
  → Capital loss = $500 × 15% = $75
  → Profit/Loss: -$75
  → DCA levels filled: [1, 2]
  
RESULT:
  - Total invested: $500
  - Coins acquired: 5.44
  - Realized loss: -$75
  - Trade closed (all positions liquidated)
  - available_budget = $1,000 - $75 = $925
```

**Key Insight**: All positions liquidated at stop price, full loss realized.

---

### Example 3: Stop-Loss Vs. Take-Profit (Same Candle)

```
CONFIG:
  stop_loss_percent = 10%
  take_profit_percent = 5%

ENTRY: anchor = $100

CANDLE DETAILS:
  high = $107
  low = $88
  (wide wick covering both extremes)

INTRA-CANDLE ORDER (per backtest algorithm):
1. Check DCA fills (low = $88)
2. Check STOP-LOSS (low = $88 <= $90 threshold)
   → STOP-LOSS TRIGGERS ✓
   → Close trade immediately
   → Skip TP check

RESULT:
  - Stop-loss executes first
  - Trade closed with loss
  - Take-profit check never happens
  - Loss recorded and budget reduced

RATIONALE:
  This is conservative and realistic. If both prices are touched
  in same candle, stop-loss executing first prevents overestimating
  profits when underlying asset is volatile.
```

**Key Insight**: Execution order matters. SL→DCA→TP prevents unrealistic scenarios.

---

### Example 4: No Stop-Loss Triggered (Normal TP)

```
CONFIG:
  initial_budget = $1,000
  stop_loss_percent = 10%
  take_profit_percent = 5%
  dca_allocations = [500, 500]
  dca_levels = [-5%, -10%]

TIMELINE:

Candle 5: Price = $95
  → Fill DCA-1 @ $95
  → Invested: $500
  → Stop threshold: $90
  → TP threshold: $95 × 1.05 = $99.75

Candle 8: Price = $100
  → Hits TP threshold ($99.75)
  → Take-profit executed ✓
  → Exit price = $99.75
  → Profit % = ($99.75 - $95) / $95 = 5%
  → Profit $ = $500 × 5% = $25
  → available_budget = $1,000 + $25 = $1,025

RESULT:
  - Stop-loss never triggered (price stayed above $90)
  - Profit taken at target
  - Capital increased for next trade
  - No loss incurred
```

**Key Insight**: When prices don't breach stop threshold, TP executes normally.

---

### Example 5: Disabled Stop-Loss (Backward Compatibility)

```
CONFIG:
  initial_budget = $1,000
  stop_loss_percent = 0  ← DISABLED
  take_profit_percent = 5%

TIMELINE:

Candle 5: Price = $95
  → Fill DCA-1

Candle 20: Price = $50 (massive crash)
  → check_stop_loss_hit(50) returns False (disabled)
  → calculate_stop_loss_threshold() returns None
  → No stop-loss action
  → Position held through crash
  → Either:
     a) Eventually hits TP if price recovers
     b) Stays in position indefinitely
     c) Backtest ends without closing

BEHAVIOR:
  - Stop-loss checks skipped entirely
  - Execution identical to pre-SL code
  - Backward compatible ✓

RESULT:
  Allows unlimited drawdown without forced exit
  (matches original system behavior)
```

**Key Insight**: `stop_loss_percent = 0` is the "disable SL" flag.

---

## Edge Cases & Handling

### Edge Case 1: Stop-Loss Threshold = Entry Price

**Scenario**: `stop_loss_percent = 100%` (nonsensical but possible)

```python
stop_threshold = anchor_price * (1 - 1.0) = 0

# Price can't go to $0 realistically
# But system should handle it:
- Any price drop triggers SL
- Most trades immediately stopped
- Effectively disables trading

VALIDATION:
→ Config should warn if stop_loss >= 50%
→ Allow but document as aggressive
```

---

### Edge Case 2: Stop-Loss = Take-Profit Price

**Scenario**: `stop_loss_percent = 5%`, `take_profit_percent = 5%`

```
anchor = $100
stop_threshold = $95
tp_threshold = $105

Price movement needed:
- To hit SL: $100 → $95 (5% down)
- To hit TP: $100 → $105 (5% up)

These are symmetric and won't conflict.

If price is volatile and touches both:
→ Whichever is touched first in candle execution order
→ Deterministic outcome
```

---

### Edge Case 3: Fractional Capital Loss

**Scenario**: Capital loss doesn't divide evenly

```
Example:
  total_invested = $333.33
  loss_pct = -12.5%
  capital_loss = 333.33 × 0.125 = $41.66625

ROUNDING:
  Use ROUND_HALF_UP to nearest cent
  capital_loss = $41.67
  available_budget -= $41.67

CONSISTENCY:
  Over many trades, rounding errors should be minimal
  If tracking critical, use Decimal arithmetic instead of float
```

---

### Edge Case 4: Position Never Fills (Edge Scenario)

**Scenario**: Entry triggered but no DCA levels fill before SL

```
Candle 5: Entry triggered
  in_trade = True
  active_dca_levels = []  # Calculated but not filled yet

Candle 6: Price drops sharply
  check_stop_loss_hit() calls calculate_stop_loss_threshold()
  → Returns None (no filled levels)
  → check_stop_loss_hit() returns False
  → No action taken

HANDLING:
  - Only trigger SL if at least one level filled
  - Empty position can't have SL
  - Prevents division errors or invalid states
```

---

### Edge Case 5: Stop-Loss Triggered But Fill Happened This Candle

**Scenario**: DCA fill and SL breach in same candle

```
Entry: anchor = $100, threshold = $90

Candle 10:
  high = $96
  low = $88
  
EXECUTION ORDER:
1. check_dca_fills(88) → fills DCA-1
   → Position now 1.0 coin @ $88
2. check_stop_loss_hit(88) → True (88 < 90)
   → Close immediately with loss
3. Skip TP check

CAPITAL LOSS:
  - Just filled @ $88
  - Immediately stopped @ $90 (threshold)
  - Net result: Loss calculated from anchor price
  - $100 → $90 = -10% loss on newly filled position

LOGIC:
  Even if filled this candle, SL still applies
  Fills are locked in before SL execution
  This is correct - prevent unrealistic no-loss scenarios
```

---

### Edge Case 6: Very Small Budget

**Scenario**: Initial budget = $10, allocation = $3 per level

```
CONFIG:
  initial_budget = $10
  dca_allocations = [3, 3, 4]
  stop_loss_percent = 20%

TRADE 1:
  Fill @ $100
  Stop @ $80
  Loss = 20% of $3 = $0.60
  available_budget = $10 - $0.60 = $9.40

TRADE 2:
  Available capital = $9.40
  DCA allocations still [3, 3, 4] = $10 total
  → ERROR: allocation > available

HANDLING:
  Option A: Scale allocations to available budget
  Option B: Skip trade if insufficient capital
  Option C: Warn and use available as max
  
RECOMMENDATION:
  Option C is cleanest
  Or detect and halt backtest gracefully
  Or require allocations < available at all times
```

---

## Statistics Recalculation Examples

### Example: Backtest with Stops

```
BACKTEST: 5 trades total

Trade 1: +$50 (TP)     → budget: $1,050
Trade 2: -$30 (SL)     → budget: $1,020
Trade 3: +$40 (TP)     → budget: $1,060
Trade 4: -$15 (SL)     → budget: $1,045
Trade 5: +$35 (TP)     → budget: $1,080

STATISTICS (Calculated):
  initial_budget = $1,000
  final_budget = $1,080
  net_pnl = +$80
  total_roi = 8.0%
  
  total_trades = 5
  winning_trades = 3 (trades 1, 3, 5)
  losing_trades = 2 (trades 2, 4)
  stopped_out_trades = 2 (trades 2, 4)
  
  win_rate = 3/5 = 60%
  stop_loss_rate = 2/5 = 40%
  
  total_profit = $50 + $40 + $35 = $125
  total_loss = $30 + $15 = $45
  
  avg_trade_pnl = $80 / 5 = $16
  largest_profit = $50
  largest_loss = -$30
  avg_profit_magnitude = $125 / 3 = $41.67
  avg_loss_magnitude = $45 / 2 = $22.50

OUTPUT:
  ✓ Stop-Loss: ENABLED (10%)
  ✓ Stopped Out: 2 trades
  ✓ Total SL Loss: -$45
  ✓ Win Rate: 60%
  ✓ Stop-Loss Rate: 40%
  ✓ ROI: +8.0%
```

---

## Testing Scenarios

### Test 1: Backward Compatibility

```python
# Run same backtest with stop_loss_percent=0 vs never specifying it
config1 = {..., "stop_loss_percent": 0.0}
config2 = {...}  # No stop_loss_percent field

strategy1 = DCAStrategy(..., stop_loss_percent=0.0)
strategy2 = DCAStrategy(...)  # Defaults to 0.0

trades1 = strategy1.run_backtest(df)
trades2 = strategy2.run_backtest(df)

assert trades1 == trades2  # Must produce identical results
assert strategy1.available_budget == strategy2.available_budget
```

### Test 2: Determinism

```python
# Same config + data = same result every time
strategy1_run1 = DCAStrategy(...).run_backtest(df)
strategy1_run2 = DCAStrategy(...).run_backtest(df)

assert strategy1_run1 == strategy1_run2  # Byte-for-byte identical
```

### Test 3: Budget Conservation

```python
# Sum of all trades must equal available_budget change
total_trades_pnl = sum(t.profit_loss for t in trades)
budget_change = final_budget - initial_budget

assert total_trades_pnl == budget_change
# No phantom gains or losses
```

### Test 4: Capital Deduction

```python
# Stopping out a trade must reduce available capital
# Next trade must use reduced capital

strategy = DCAStrategy(initial_budget=1000)
# ... setup and trade ...
# After SL hit:
assert strategy.available_budget < 1000  # Reduced
# Next DCA allocation must not exceed available_budget
```

### Test 5: SL Before TP

```python
# If both triggered same candle, SL executes
# Create data where both thresholds touched:
# candle = (low=85, high=110)
# stop_threshold = 90
# tp_threshold = 105

# Both triggered: low <= 90 AND high >= 105
# Expected: SL executes, TP skipped, result = loss
```

---

## Configuration Examples

### Conservative (Tight Stop-Loss)

```json
{
  "initial_budget": 10000,
  "stop_loss_percent": 5.0,
  "dca_levels": [-2, -4, -6],
  "take_profit_percent": 3.0
}
```

**Characteristics**:
- Quick loss exit (5% drawdown)
- Tight profit target (3%)
- Frequent trades, smaller P&L
- Higher stop-loss rate

---

### Moderate (Balanced)

```json
{
  "initial_budget": 10000,
  "stop_loss_percent": 10.0,
  "dca_levels": [-3, -6, -9, -12],
  "take_profit_percent": 5.0
}
```

**Characteristics**:
- Standard risk tolerance
- Balanced P&L expectations
- Moderate stop-loss rate
- Good for most assets

---

### Aggressive (Wide Stop-Loss)

```json
{
  "initial_budget": 10000,
  "stop_loss_percent": 20.0,
  "dca_levels": [-5, -10, -15, -20, -25],
  "take_profit_percent": 10.0
}
```

**Characteristics**:
- Tolerates larger drawdowns
- Waits for bigger profits
- Fewer but larger trades
- Low stop-loss rate
- Higher risk/reward

---

### No Stop-Loss (Original)

```json
{
  "initial_budget": 10000,
  "stop_loss_percent": 0.0,
  "dca_levels": [-2, -4, -8, -12, -16],
  "take_profit_percent": 5.0
}
```

**Characteristics**:
- Unlimited downside
- Positions never forced closed
- Matches pre-SL behavior
- Can result in large drawdowns

---

## Debugging Tips

### Check if Stop-Loss Calculation is Correct

```python
strategy.anchor_price = 100
strategy.stop_loss_percent = 10

threshold = strategy.calculate_stop_loss_threshold()
print(f"Threshold: {threshold}")  # Should be 90.0

# Manual check:
assert threshold == 100 * (1 - 0.10)  # 90
```

### Trace Stop-Loss Hit in Backtest

```python
if strategy.check_stop_loss_hit(candle_low):
    threshold = strategy.calculate_stop_loss_threshold()
    print(f"🛑 SL HIT: candle.low={candle_low} <= threshold={threshold}")
    print(f"   Anchor={strategy.anchor_price}, SL%={strategy.stop_loss_percent}%")
```

### Verify Budget Updates

```python
print(f"Before:  {strategy.available_budget}")
trade, new_budget = strategy.close_trade_with_loss(...)
strategy.available_budget = new_budget
print(f"After:   {strategy.available_budget}")
print(f"Loss:    {trade.profit_loss}")

# Verify: available_budget_before + profit_loss = available_budget_after
assert old_budget + trade.profit_loss == strategy.available_budget
```

### Print Full Trade Info with Stop-Loss

```python
for trade in strategy.completed_trades:
    if trade.stop_loss_triggered:
        print(f"🛑 Trade #{i}: SL @ {trade.stop_loss_price}")
        print(f"   Loss: {trade.stop_loss_loss}")
        print(f"   Reason: {trade.completion_reason}")
```
