# Stop-Loss Architecture Diagram

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKTEST SYSTEM                             │
└─────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────┐
                    │  strategy_config.json    │
                    │                          │
                    │ • initial_budget: 8000   │
                    │ • stop_loss_percent: 10  │ ← NEW PARAMETER
                    │ • dca_levels: [...]      │
                    │ • take_profit_percent: 5 │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │  StrategyConfig          │
                    │  (config_loader.py)      │
                    │                          │
                    │ @property                │
                    │ stop_loss_percent()      │ ← NEW
                    │                          │
                    │ Validation:              │
                    │ • stop_loss >= 0         │
                    │ • Warn if > 50%          │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │  DCAStrategy             │
                    │  (dca_strategy.py)       │
                    │                          │
                    │ __init__:                │
                    │ • initial_budget         │
                    │ • stop_loss_percent ← NEW
                    │ • available_budget ← NEW │
                    └────────────┬─────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
           ▼                     ▼                     ▼
    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
    │ DCA Levels   │      │Risk Control  │      │Backtest Loop │
    │(existing)    │      │(NEW)         │      │(modified)    │
    │              │      │              │      │              │
    │• Fills       │      │• SL Calc     │      │• available   │
    │• Prices      │      │• SL Check    │      │  _budget     │
    │• Tracking    │      │• SL Close    │      │• Budget      │
    │              │      │              │      │  updates     │
    └──────────────┘      └──────────────┘      └──────────────┘
```

---

## Control Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    run_backtest(df)                                 │
│                                                                     │
│  available_budget = initial_budget  ← NEW                          │
│  completed_trades = []                                             │
│                                                                     │
│  for each candle in df:                                            │
│    ┌─────────────────────────────────────────────────────────┐   │
│    │ NOT IN TRADE?                                           │   │
│    ├─────────────────────────────────────────────────────────┤   │
│    │ ✓ Yes                                                   │   │
│    │ ├─ Update anchor_price                                  │   │
│    │ ├─ Check entry trigger (candle.low <= first DCA level) │   │
│    │ └─ If triggered → Start trade, fill DCA levels         │   │
│    │ ✗ No → Continue to IN_TRADE section                    │   │
│    └─────────────────────────────────────────────────────────┘   │
│                                                                     │
│    ┌─────────────────────────────────────────────────────────┐   │
│    │ IN TRADE                                                │   │
│    ├─────────────────────────────────────────────────────────┤   │
│    │                                                         │   │
│    │ STEP 1: Check DCA Fills (candle.low <= entry_price)    │   │
│    │ ├─ newly_filled = check_dca_fills(candle_low)          │   │
│    │ └─ Update position (coins, avg_price)                  │   │
│    │                                                         │   │
│    │ STEP 2: ★ CHECK STOP-LOSS (NEW - BEFORE TP)            │   │
│    │ ├─ threshold = calculate_stop_loss_threshold()          │   │
│    │ ├─ if threshold is None → Skip (disabled)              │   │
│    │ ├─ if check_stop_loss_hit(candle_low) == True:         │   │
│    │ │  └─ ★ STOP-LOSS TRIGGERED                            │   │
│    │ │     ├─ trade, available_budget =                     │   │
│    │ │     │   close_trade_with_loss(...)                   │   │
│    │ │     ├─ Reset position                                │   │
│    │ │     ├─ Continue to next candle (skip TP check)       │   │
│    │ │     └─ ★ available_budget -= capital_loss            │   │
│    │ └─ If no SL → Proceed to STEP 3                        │   │
│    │                                                         │   │
│    │ STEP 3: Check Take-Profit (candle.high >= tp_price)    │   │
│    │ ├─ if check_take_profit_hit(candle_high) == True:      │   │
│    │ │  ├─ TAKE-PROFIT HIT                                  │   │
│    │ │  ├─ trade = close_trade(...)                         │   │
│    │ │  ├─ ★ available_budget += trade.profit_loss          │   │
│    │ │  ├─ Reset position                                   │   │
│    │ │  └─ Set new anchor = candle.high                     │   │
│    │ └─ If no TP → Hold position, continue next candle      │   │
│    │                                                         │   │
│    └─────────────────────────────────────────────────────────┘   │
│                                                                     │
│  return completed_trades                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

KEY CHANGES (★):
  1. available_budget tracking throughout
  2. Stop-loss check before take-profit
  3. Budget deduction on loss
  4. Budget increase on profit
```

---

## Stop-Loss Calculation Logic

```
┌────────────────────────────────────────────────────────┐
│  calculate_stop_loss_threshold()                       │
├────────────────────────────────────────────────────────┤
│                                                        │
│  if stop_loss_percent <= 0:                           │
│    return None  ← DISABLED                            │
│                                                        │
│  filled_levels = [l for l in active_dca_levels        │
│                   if l.filled]                        │
│                                                        │
│  if not filled_levels:                                │
│    return None  ← No position yet                     │
│                                                        │
│  # Formula:                                           │
│  # threshold = anchor_price × (1 - stop_loss_pct)    │
│  #                                                    │
│  # Example:                                           │
│  # anchor = $100, stop_loss = 10%                    │
│  # threshold = $100 × 0.90 = $90                     │
│                                                        │
│  threshold = anchor_price *                           │
│              (1 - stop_loss_percent / 100)            │
│                                                        │
│  return threshold                                     │
│                                                        │
└────────────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────┐
│  check_stop_loss_hit(candle_low)                       │
├────────────────────────────────────────────────────────┤
│                                                        │
│  threshold = calculate_stop_loss_threshold()          │
│                                                        │
│  if threshold is None:                                │
│    return False  ← Disabled or no position            │
│                                                        │
│  # Trigger if wick touches or goes below threshold   │
│  return candle_low <= threshold                       │
│                                                        │
│  Examples:                                            │
│    threshold=90, candle_low=90 → True ✓              │
│    threshold=90, candle_low=88 → True ✓              │
│    threshold=90, candle_low=92 → False ✗             │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## Loss Calculation & Budget Update Flow

```
┌─────────────────────────────────────────────────────────────┐
│  close_trade_with_loss(exit_time, loss_price,              │
│                        available_budget)                    │
│                                                             │
│  Input:                                                     │
│    exit_time: Timestamp of SL execution                    │
│    loss_price: Price at which SL triggered                 │
│    available_budget: Current available capital             │
│                                                             │
│  Process:                                                   │
│  ┌───────────────────────────────────────────────┐        │
│  │ Step 1: Calculate Loss Percentage             │        │
│  │ ─────────────────────────────────────────────  │        │
│  │ loss_pct = (loss_price - anchor_price) /     │        │
│  │            anchor_price × 100                │        │
│  │                                               │        │
│  │ Example:                                      │        │
│  │   loss_price = $85                           │        │
│  │   anchor_price = $100                        │        │
│  │   loss_pct = (85-100)/100 × 100 = -15%      │        │
│  └───────────────────────────────────────────────┘        │
│                                                             │
│  ┌───────────────────────────────────────────────┐        │
│  │ Step 2: Calculate Capital Loss (Absolute)     │        │
│  │ ─────────────────────────────────────────────  │        │
│  │ capital_loss = abs(loss_pct / 100) ×         │        │
│  │               total_invested                  │        │
│  │                                               │        │
│  │ Example:                                      │        │
│  │   loss_pct = -15%                            │        │
│  │   total_invested = $1,000                    │        │
│  │   capital_loss = 0.15 × 1,000 = $150         │        │
│  └───────────────────────────────────────────────┘        │
│                                                             │
│  ┌───────────────────────────────────────────────┐        │
│  │ Step 3: Update Available Budget                │        │
│  │ ─────────────────────────────────────────────  │        │
│  │ updated_budget = available_budget -           │        │
│  │                  capital_loss                 │        │
│  │                                               │        │
│  │ Example:                                      │        │
│  │   available_budget = $10,000                  │        │
│  │   capital_loss = $150                         │        │
│  │   updated_budget = 10,000 - 150 = $9,850    │        │
│  └───────────────────────────────────────────────┘        │
│                                                             │
│  ┌───────────────────────────────────────────────┐        │
│  │ Step 4: Create Trade Record                    │        │
│  │ ─────────────────────────────────────────────  │        │
│  │ trade = Trade(                                │        │
│  │   ..., profit_loss = -capital_loss,           │        │
│  │   stop_loss_triggered = True,                 │        │
│  │   completion_reason = "stop_loss",            │        │
│  │   ...                                         │        │
│  │ )                                             │        │
│  └───────────────────────────────────────────────┘        │
│                                                             │
│  Output:                                                    │
│    (Trade, updated_budget)                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘

★ CRITICAL: updated_budget is returned and used immediately
           to reduce available capital for next trades
```

---

## Data Structure Dependencies

```
┌─────────────────────────────────────────────────┐
│            Trade Dataclass                      │
├─────────────────────────────────────────────────┤
│ Existing Fields:                                │
│ • start_time, end_time, anchor_price,           │
│ • deepest_level, deepest_price                  │
│ • exit_price, total_invested, total_return      │
│ • profit_loss, profit_percent                   │
│ • dca_levels_filled                             │
│                                                 │
│ NEW Fields:                                     │
│ • stop_loss_triggered: bool = False             │
│ • stop_loss_price: Optional[float] = None       │
│ • stop_loss_loss: float = 0.0                   │
│ • completion_reason: str = "take_profit"        │
│                     enum: "take_profit"         │
│                           "stop_loss"           │
└─────────────────────────────────────────────────┘
                        │
                        │ Used by
                        ▼
┌─────────────────────────────────────────────────┐
│      BacktestResults Dataclass (NEW)            │
├─────────────────────────────────────────────────┤
│ Budget Tracking:                                │
│ • initial_budget, final_budget                  │
│                                                 │
│ Trade Counts:                                   │
│ • total_trades, winning_trades                  │
│ • losing_trades, stopped_out_trades ← NEW       │
│                                                 │
│ Profit/Loss:                                    │
│ • total_profit, total_loss, net_pnl             │
│                                                 │
│ Metrics:                                        │
│ • total_roi, win_rate, stop_loss_rate ← NEW     │
│ • avg_trade_pnl, avg_profit/loss_magnitude      │
│ • largest_profit, largest_loss                  │
│                                                 │
│ Duration:                                       │
│ • avg_trade_duration_days, total_test_days      │
└─────────────────────────────────────────────────┘
                        │
                        │ Created by
                        ▼
┌─────────────────────────────────────────────────┐
│    calculate_backtest_results()                 │
│    (DCAStrategy method - NEW)                   │
└─────────────────────────────────────────────────┘
```

---

## Statistical Calculation Flow

```
┌────────────────────────────────────────────────────┐
│  calculate_backtest_results()                      │
├────────────────────────────────────────────────────┤
│                                                    │
│  Input: List[Trade] completed_trades              │
│                                                    │
│  ┌──────────────────────────────────────────┐    │
│  │ Separate by outcome                      │    │
│  ├──────────────────────────────────────────┤    │
│  │ winning = [t for t in trades            │    │
│  │           if t.profit_loss > 0]          │    │
│  │ losing = [t for t in trades             │    │
│  │          if t.profit_loss < 0]           │    │
│  │ stopped = [t for t in trades ★ NEW      │    │
│  │           if t.stop_loss_triggered]      │    │
│  └──────────────────────────────────────────┘    │
│                                                    │
│  ┌──────────────────────────────────────────┐    │
│  │ Calculate totals                         │    │
│  ├──────────────────────────────────────────┤    │
│  │ total_profit = sum(winning.profit_loss)  │    │
│  │ total_loss = abs(sum(losing.profit_loss))│    │
│  │ net_pnl = sum(all.profit_loss)           │    │
│  │ final_budget = initial + net_pnl         │    │
│  └──────────────────────────────────────────┘    │
│                                                    │
│  ┌──────────────────────────────────────────┐    │
│  │ Calculate rates                          │    │
│  ├──────────────────────────────────────────┤    │
│  │ total_roi = (final - initial) /          │    │
│  │             initial × 100                │    │
│  │ win_rate = len(winning) / total × 100    │    │
│  │ stop_loss_rate = len(stopped) /  ★ NEW  │    │
│  │                  total × 100             │    │
│  └──────────────────────────────────────────┘    │
│                                                    │
│  ┌──────────────────────────────────────────┐    │
│  │ Calculate averages                       │    │
│  ├──────────────────────────────────────────┤    │
│  │ avg_trade_pnl = net_pnl / total          │    │
│  │ avg_profit_mag = total_profit /          │    │
│  │                  len(winning)            │    │
│  │ avg_loss_mag = total_loss / len(losing)  │    │
│  └──────────────────────────────────────────┘    │
│                                                    │
│  Output: BacktestResults                         │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## Configuration Validation Flow

```
┌──────────────────────────────────────────────────┐
│  StrategyConfig._validate_config()               │
├──────────────────────────────────────────────────┤
│                                                  │
│  Existing validations:                           │
│  ✓ DCA levels negative & sorted                  │
│  ✓ DCA allocations positive                      │
│  ✓ Initial budget positive                       │
│  ✓ Take profit positive                          │
│                                                  │
│  NEW validations:                                │
│  ─────────────────────────────────────────────── │
│  if stop_loss_percent < 0:                       │
│    raise ValueError(                             │
│      "stop_loss_percent must be >= 0"            │
│    )                                             │
│                                                  │
│  if stop_loss_percent >= 50:                     │
│    print("⚠️  WARNING: Very aggressive SL"       │
│          f" ({stop_loss_percent}%)")             │
│                                                  │
│  Valid ranges:                                   │
│  • 0 = Disabled (backward compatible) ✓          │
│  • 0 < x < 50 = Normal ✓                         │
│  • >= 50 = Warning (allowed but aggressive)      │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## Backward Compatibility Guarantee

```
┌─────────────────────────────────────────────────────┐
│  When stop_loss_percent = 0 (DISABLED)              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  calculate_stop_loss_threshold()                    │
│    → Returns None                                   │
│                                                     │
│  check_stop_loss_hit(any_price)                     │
│    → Returns False (always)                         │
│                                                     │
│  Execution in run_backtest():                       │
│    if check_stop_loss_hit(...):  ← Always False     │
│      # This block NEVER executes                    │
│                                                     │
│  Result:                                            │
│  ✓ No stop-loss logic runs                          │
│  ✓ Identical to pre-SL code                         │
│  ✓ Backward compatible                              │
│  ✓ Same trades, same results                        │
│                                                     │
│  Verification:                                      │
│    backtest_with_SL(stop_loss=0) ==                 │
│    backtest_without_SL()                            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Implementation Dependency Graph

```
Phase 1: Configuration & Validation
  └─ config_loader.py
     ├─ Add stop_loss_percent property
     └─ Add validation logic

Phase 2: Data Structures
  └─ dca_strategy.py
     ├─ Extend Trade dataclass
     └─ Add BacktestResults dataclass

Phase 3: Core Logic
  └─ dca_strategy.py
     ├─ calculate_stop_loss_threshold()
     ├─ check_stop_loss_hit()
     └─ close_trade_with_loss()

Phase 4: Backtest Integration
  └─ dca_strategy.py
     ├─ Modify run_backtest() loop
     ├─ Add available_budget tracking
     └─ Insert SL check before TP

Phase 5: Statistics
  └─ dca_strategy.py
     ├─ calculate_backtest_results()
     └─ update print_backtest_results()

Phase 6: Integration
  └─ run_backtest.py
     └─ Pass stop_loss_percent to strategy

All phases depend on Phase 1 (config exists)
Phases 2-3 can happen in parallel
Phase 4 depends on Phases 2-3
Phase 5 depends on Phase 4
Phase 6 depends on Phase 5
```

---

## Key Files Modification Summary

```
1. strategy_config.json (2 lines)
   + "stop_loss_percent": 10.0

2. config_loader.py (10 lines)
   + @property stop_loss_percent()
   + Validation in _validate_config()

3. dca_strategy.py (200+ lines)
   + Trade dataclass: 4 new fields
   + BacktestResults dataclass: NEW
   + DCAStrategy.__init__: 1 new parameter
   + calculate_stop_loss_threshold(): NEW method
   + check_stop_loss_hit(): NEW method
   + close_trade_with_loss(): NEW method
   + calculate_backtest_results(): NEW method
   + run_backtest(): Modified (SL check added)
   + print_backtest_results(): Updated output

4. run_backtest.py (1 line)
   + Pass stop_loss_percent to strategy constructor

Total impact: Minimal changes to existing code
             Large addition of new stop-loss logic
             No breaking changes
```
