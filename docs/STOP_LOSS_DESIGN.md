# Stop-Loss Implementation Design

## Executive Summary

This document details a comprehensive stop-loss mechanism for your DCA simulation system. The design ensures:
- **Financial correctness**: Losses reduce available capital deterministically
- **Statistical consistency**: All metrics recalculated with proper accounting
- **Clean architecture**: Stop-loss logic isolated from core trading logic
- **Backward compatibility**: Existing behavior preserved when `stop_loss_percent = 0`

---

## Current System Architecture

### Core Components

```
dca_strategy.py
├── DCAStrategy (main orchestrator)
│   ├── Trade (completed trade record)
│   └── DCALevel (single DCA entry point)
└── run_backtest() (main backtest loop)

config_loader.py
├── StrategyConfig (configuration parser)
└── Validation logic

run_backtest.py
└── Main entry point + results printer
```

### Current Execution Flow

```
1. Load config + data
2. Initialize strategy with initial_budget
3. For each candle:
   a. If not in trade:
      - Update anchor price
      - Detect trade entry (price drops to first DCA level)
   b. If in trade:
      - Check DCA fills: if candle.low <= pi, fill level
      - Check TP: if candle.high >= tp_price, close trade
4. Print results (total P&L, ROI, trades)
```

### Current Trade Lifecycle

```
State: NOT_IN_TRADE
  → Anchor price = candle.high
  → Wait for dump to first DCA level

State: IN_TRADE
  → Fill DCA levels as price drops (candle.low <= pi)
  → Calculate TP price = avg_price * (1 + TP%)
  → On TP hit (candle.high >= tp_price):
      - Close trade, record profit/loss
      - Reset position completely
      - Back to NOT_IN_TRADE

Result: List[Trade] → Summary statistics
```

---

## Stop-Loss Architecture & Design

### 1. Configuration Layer

**Add to `strategy_config.json`:**

```json
{
  "initial_budget": 8000,
  "stop_loss_percent": 10.0,  // NEW: 0 = disabled, >0 = enabled
  "dca_levels": [-2, -4, -8, -12, -16, -20, -24, -28],
  "dca_allocations": [30, 60, 120, 240, 480, 960, 1920, 3840],
  "take_profit_percent": 5.0
}
```

**Validation in `config_loader.py`:**

```python
@property
def stop_loss_percent(self) -> float:
    """Get stop-loss percentage (0 = disabled)"""
    return self.config.get('stop_loss_percent', 0.0)

def _validate_config(self):
    # ... existing validation ...
    
    # Validate stop loss
    if self.config.get('stop_loss_percent', 0) < 0:
        raise ValueError("Stop loss percent must be >= 0")
```

### 2. Core Trade Mechanics

#### Concepts

```
STOP-LOSS TRIGGER CONDITION:
- Establish entry_price when first DCA level fills
- Calculate loss_threshold = entry_price * (1 - stop_loss_percent)
- On each candle: if candle.low <= loss_threshold → STOP LOSS HIT

LOSS CALCULATION:
- Unrealized loss at stop price = (stop_price - entry_price) / entry_price * 100
- Capital lost = -unrealized_loss% * total_invested
- Example:
  - entry_price = $100
  - stop_loss_percent = 10%
  - stop_price = $90
  - Capital invested = $1,000
  - Capital lost = 1,000 * 0.10 = $100
  - Remaining capital = 9,000 - 100 = 8,900
```

#### Position State Enhancement

```python
@dataclass
class Trade:
    """Represents a completed trade cycle"""
    # ... existing fields ...
    
    # Stop-loss tracking
    stop_loss_triggered: bool = False  # NEW
    stop_loss_price: Optional[float] = None  # NEW
    stop_loss_loss: float = 0.0  # NEW: actual loss amount
    
    # Completion reason
    completion_reason: str = "take_profit"  # NEW: "take_profit" or "stop_loss"

@dataclass
class RiskMetrics:
    """NEW: Track risk-related metrics per trade"""
    entry_price: float
    stop_loss_threshold: Optional[float]
    loss_threshold: Optional[float]
    lowest_price_reached: float
```

### 3. Execution Logic

#### Modified Run Backtest Flow

```
1. Initialize strategy with initial_budget
2. available_budget = initial_budget (NEW: tracks real capital)

3. For each candle:
   
   a. If NOT_IN_TRADE:
      - Update anchor price
      - If entry trigger:
          * Start trade
          * entry_price = anchor_price
          * Calculate stop_loss_level (if enabled)
   
   b. If IN_TRADE:
      - Check DCA fills → update position
      - Calculate current unrealized P&L
      - 🆕 CHECK STOP-LOSS (before TP check)
        * if candle.low <= loss_threshold:
            - Close trade with LOSS
            - capital_lost = abs(unrealized_loss) * total_invested
            - available_budget -= capital_lost (UPDATE BUDGET)
            - Reset position
            - Skip TP check for this candle
      
      - 🆕 Check TP (only if not stopped)
        * if candle.high >= tp_price:
            - Close trade with PROFIT
            - capital_gain = profit * total_invested / 100
            - available_budget += capital_gain
            - Reset position
```

#### Detailed Stop-Loss Logic

```python
def calculate_stop_loss_threshold(self) -> Optional[float]:
    """
    Calculate price level that triggers stop-loss
    
    ONLY valid after first DCA level fills.
    Uses the anchor price as entry reference.
    
    Returns: price <= this value triggers stop loss
    """
    if self.stop_loss_percent == 0:
        return None  # Stop-loss disabled
    
    filled_levels = [lvl for lvl in self.active_dca_levels if lvl.filled]
    if not filled_levels:
        return None  # No position yet
    
    # Use anchor price as entry reference
    entry_price = self.anchor_price
    
    # Stop loss threshold = entry * (1 - stop_loss_pct)
    # Example: entry=$100, stop_loss=10% → threshold=$90
    threshold = entry_price * (1 - self.stop_loss_percent / 100)
    
    return threshold

def check_stop_loss_hit(self, candle_low: float) -> bool:
    """
    Check if stop-loss level was breached
    
    Execution rule: SL triggers if candle.low <= threshold
    
    Args:
        candle_low: Lowest price of current candle
        
    Returns:
        True if stop-loss was triggered
    """
    threshold = self.calculate_stop_loss_threshold()
    if threshold is None:
        return False
    
    return candle_low <= threshold

def close_trade_with_loss(
    self, 
    exit_time: pd.Timestamp, 
    loss_price: float,
    available_budget: float
) -> tuple[Trade, float]:
    """
    Close trade due to stop-loss
    
    CRITICAL: Calculates actual capital loss and reduces available budget
    
    Args:
        exit_time: Timestamp of exit
        loss_price: Price at stop-loss execution
        available_budget: Current available capital (before loss deduction)
    
    Returns:
        (Trade object, updated_available_budget)
    """
    filled_levels = [lvl for lvl in self.active_dca_levels if lvl.filled]
    total_invested = sum(lvl.budget_allocation for lvl in filled_levels)
    
    # Calculate unrealized loss percentage at stop price
    # loss_pct = (loss_price - entry_price) / entry_price * 100
    loss_pct = ((loss_price - self.anchor_price) / self.anchor_price) * 100
    
    # Capital loss amount
    # Example: total_invested=1000, loss_pct=-10% → loss=100
    capital_loss = abs(loss_pct / 100 * total_invested)
    
    # Updated budget after loss
    updated_budget = available_budget - capital_loss
    
    # Create trade record
    trade = Trade(
        start_time=self.trade_start_time,
        end_time=exit_time,
        anchor_price=self.anchor_price,
        deepest_level=self.get_deepest_filled_level().level_num,
        deepest_price=self.get_deepest_filled_level().fill_price,
        exit_price=loss_price,
        total_invested=total_invested,
        total_return=0,  # No return, all capital lost/converted
        profit_loss=-capital_loss,  # Negative = loss
        profit_percent=loss_pct,
        dca_levels_filled=[lvl.level_num for lvl in filled_levels],
        stop_loss_triggered=True,  # NEW
        stop_loss_price=loss_price,  # NEW
        stop_loss_loss=capital_loss,  # NEW
        completion_reason="stop_loss"  # NEW
    )
    
    self.completed_trades.append(trade)
    return trade, updated_budget
```

### 4. Statistics & Accounting

#### Metrics Recalculation

```python
class BacktestResults:
    """NEW: Comprehensive backtest statistics"""
    
    initial_budget: float
    final_budget: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    stopped_out_trades: int  # NEW: trades closed by stop-loss
    
    # Profit/Loss accounting
    total_profit: float
    total_loss: float
    total_roi: float
    avg_trade_pnl: float
    
    # Win rate & probabilities
    win_rate: float
    stop_loss_rate: float  # NEW: % of trades stopped
    
    # Risk metrics
    largest_loss: float
    largest_profit: float
    avg_loss_magnitude: float
    avg_profit_magnitude: float

def calculate_backtest_results(trades: List[Trade], initial_budget: float) -> BacktestResults:
    """
    Recalculate all statistics with stop-loss impact
    
    CRITICAL: Must account for capital reductions from losses
    """
    if not trades:
        return BacktestResults(
            initial_budget=initial_budget,
            final_budget=initial_budget,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            stopped_out_trades=0,
            total_profit=0,
            total_loss=0,
            total_roi=0,
            avg_trade_pnl=0,
            win_rate=0,
            stop_loss_rate=0,
            largest_loss=0,
            largest_profit=0,
            avg_loss_magnitude=0,
            avg_profit_magnitude=0
        )
    
    # Separate trades by outcome
    winning_trades = [t for t in trades if t.profit_loss > 0]
    losing_trades = [t for t in trades if t.profit_loss < 0]
    stopped_out_trades = [t for t in trades if t.stop_loss_triggered]
    
    # Aggregate calculations
    total_profit = sum(t.profit_loss for t in winning_trades)
    total_loss = sum(t.profit_loss for t in losing_trades)  # Already negative
    
    # Final budget = initial + all P&L
    final_budget = initial_budget + sum(t.profit_loss for t in trades)
    
    # ROI = (final - initial) / initial
    total_roi = ((final_budget - initial_budget) / initial_budget * 100) if initial_budget > 0 else 0
    
    # Rates
    total_trades = len(trades)
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    stop_loss_rate = (len(stopped_out_trades) / total_trades * 100) if total_trades > 0 else 0
    
    # Averages
    avg_trade_pnl = sum(t.profit_loss for t in trades) / total_trades if total_trades > 0 else 0
    avg_loss_magnitude = abs(sum(t.profit_loss for t in losing_trades) / len(losing_trades)) if losing_trades else 0
    avg_profit_magnitude = sum(t.profit_loss for t in winning_trades) / len(winning_trades) if winning_trades else 0
    
    # Extremes
    largest_loss = min(t.profit_loss for t in trades) if trades else 0
    largest_profit = max(t.profit_loss for t in trades) if trades else 0
    
    return BacktestResults(
        initial_budget=initial_budget,
        final_budget=final_budget,
        total_trades=total_trades,
        winning_trades=len(winning_trades),
        losing_trades=len(losing_trades),
        stopped_out_trades=len(stopped_out_trades),
        total_profit=total_profit,
        total_loss=total_loss,
        total_roi=total_roi,
        avg_trade_pnl=avg_trade_pnl,
        win_rate=win_rate,
        stop_loss_rate=stop_loss_rate,
        largest_loss=largest_loss,
        largest_profit=largest_profit,
        avg_loss_magnitude=avg_loss_magnitude,
        avg_profit_magnitude=avg_profit_magnitude
    )
```

---

## Modified Backtest Loop

```python
def run_backtest(self, df: pd.DataFrame) -> List[Trade]:
    """
    Enhanced backtest with stop-loss support
    """
    self.reset_game()
    self.completed_trades = []
    available_budget = self.initial_budget  # NEW: track real capital
    
    for idx, row in df.iterrows():
        timestamp = row['datetime']
        candle_high = row['high']
        candle_low = row['low']
        
        if not self.in_trade:
            if self.anchor_price is None:
                self.anchor_price = candle_high
                continue
            
            dump_from_anchor = ((candle_low - self.anchor_price) / self.anchor_price) * 100
            
            if dump_from_anchor <= self.dca_levels[0]:
                self.in_trade = True
                self.trade_start_time = timestamp
                self.active_dca_levels = self.calculate_dca_prices(self.anchor_price)
                self.check_dca_fills(candle_low)
            else:
                self.anchor_price = max(self.anchor_price, candle_high)
        
        else:
            # In trade - check events in order
            newly_filled = self.check_dca_fills(candle_low)
            
            # 🆕 STOP-LOSS CHECK (executes before TP)
            if self.check_stop_loss_hit(candle_low):
                sl_price = self.calculate_stop_loss_threshold()
                trade, available_budget = self.close_trade_with_loss(
                    timestamp, 
                    sl_price, 
                    available_budget
                )
                self.reset_game()
                self.anchor_price = candle_high
                continue  # Skip TP check for this candle
            
            # Take-profit check (only if not stopped)
            if self.check_take_profit_hit(candle_high):
                tp_price = self.calculate_take_profit_price()
                trade = self.close_trade(timestamp, tp_price)
                # Update available budget with profit
                available_budget += trade.profit_loss  # NEW
                self.reset_game()
                self.anchor_price = candle_high
    
    return self.completed_trades
```

---

## Edge Cases & Handling

### 1. Stop-Loss Triggered Same Candle as Entry

**Scenario**: Candle opens with both DCA fill AND stop-loss breach

**Handling**:
```
Execution Order (per candle):
1. Check DCA fills (order: candle.low <= pi)
2. Check stop-loss (order: candle.low <= threshold)
3. Check TP (order: candle.high >= tp_price)

If stop-loss AND TP both triggered same candle:
→ Process in order above
→ Stop-loss executes first (closes trade)
→ Skip TP check for this candle
```

### 2. Stop-Loss Disabled vs. Enabled

**When `stop_loss_percent = 0`:**
- `calculate_stop_loss_threshold()` returns `None`
- `check_stop_loss_hit()` always returns `False`
- Stop-loss logic never executes
- All statistics calculated normally
- **Backward compatible** ✓

**When `stop_loss_percent > 0`:**
- Stop-loss logic executes every candle in trade
- Losses immediately deducted from available_budget
- Affects future trade calculations
- Statistics include stop-loss metrics

### 3. Multiple DCA Fills Before Stop-Loss

**Scenario**: Trade spans 10 candles, fills 3 DCA levels, then hit stop-loss

**Handling**:
```
Candle 1: Fills DCA-1 @ $95
Candle 5: Fills DCA-2 @ $90
Candle 8: Fills DCA-3 @ $85
Candle 9: Hits stop-loss @ $80 (below entry threshold)

Capital loss calculation:
- Total invested = $95*Q1 + $90*Q2 + $85*Q3
- Entry price = anchor (original ref price)
- Loss % = (80 - anchor) / anchor * 100
- Capital lost = Loss% * Total invested
- Available budget reduced by capital_lost

Result: Clean accounting, all invested capital accounted for
```

### 4. Fractional Capital (Rounding)

**Issue**: Capital loss may not divide evenly; need deterministic handling

**Solution**:
```python
# Use ROUND_HALF_UP to avoid accumulation errors
from decimal import Decimal, ROUND_HALF_UP

capital_loss = float(Decimal(str(loss_amt)).quantize(
    Decimal('0.01'), rounding=ROUND_HALF_UP
))
available_budget = float(Decimal(str(available_budget)).quantize(
    Decimal('0.01'), rounding=ROUND_HALF_UP
)) - capital_loss
```

### 5. Stop-Loss Below 0% (Logical)

**Scenario**: Stop-loss triggers when P < 0 (shouldn't happen)

**Validation**: Config validates `stop_loss_percent >= 0`

**Runtime safety**:
```python
if self.stop_loss_percent < 0:
    raise ValueError("Stop loss must be >= 0")
```

---

## Implementation Checklist

### Phase 1: Configuration & Validation
- [ ] Add `stop_loss_percent` to `strategy_config.json`
- [ ] Add validation in `config_loader.py`
- [ ] Update `StrategyConfig.stop_loss_percent` property
- [ ] Test edge cases (0, negative, very high values)

### Phase 2: Data Structures
- [ ] Add fields to `Trade` dataclass
- [ ] Create `RiskMetrics` dataclass
- [ ] Create `BacktestResults` dataclass

### Phase 3: Core Logic
- [ ] Implement `calculate_stop_loss_threshold()`
- [ ] Implement `check_stop_loss_hit()`
- [ ] Implement `close_trade_with_loss()`
- [ ] Modify `run_backtest()` loop
- [ ] Add `available_budget` tracking

### Phase 4: Statistics
- [ ] Implement `calculate_backtest_results()`
- [ ] Update `print_backtest_results()` display
- [ ] Add stop-loss metrics to output
- [ ] Test with example trades

### Phase 5: Testing
- [ ] Test with `stop_loss_percent = 0` (backward compat)
- [ ] Test with `stop_loss_percent = 10` (enable SL)
- [ ] Test edge cases (same-candle entry+SL, multiple DCA fills, etc.)
- [ ] Validate budget accounting across multiple trades
- [ ] Verify ROI calculations

### Phase 6: Documentation
- [ ] Update README with stop-loss parameter
- [ ] Add examples to ALGORITHM_SPECIFICATION.md
- [ ] Document output changes
- [ ] Add to trade summary output

---

## Code Templates

### Template 1: Enhanced Trade Dataclass

```python
@dataclass
class Trade:
    """Represents a completed trade cycle"""
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    anchor_price: float
    deepest_level: int
    deepest_price: float
    exit_price: float
    total_invested: float
    total_return: float
    profit_loss: float
    profit_percent: float
    dca_levels_filled: List[int]
    
    # NEW: Stop-loss tracking
    stop_loss_triggered: bool = False
    stop_loss_price: Optional[float] = None
    stop_loss_loss: float = 0.0
    completion_reason: str = "take_profit"  # "take_profit" | "stop_loss"
```

### Template 2: Available Budget Tracking

```python
class DCAStrategy:
    def __init__(self, initial_budget: float, stop_loss_percent: float = 0, ...):
        self.initial_budget = initial_budget
        self.stop_loss_percent = stop_loss_percent
        self.available_budget = initial_budget  # NEW
        # ... rest of init
    
    def run_backtest(self, df: pd.DataFrame) -> List[Trade]:
        self.reset_game()
        self.available_budget = self.initial_budget  # NEW
        
        for idx, row in df.iterrows():
            # ... backtest loop ...
            
            if self.in_trade:
                # Stop-loss check
                if self.check_stop_loss_hit(candle_low):
                    trade, self.available_budget = self.close_trade_with_loss(
                        timestamp, 
                        sl_price, 
                        self.available_budget  # NEW: pass current budget
                    )
                    # ...
                
                # Take-profit check
                elif self.check_take_profit_hit(candle_high):
                    trade = self.close_trade(timestamp, tp_price)
                    self.available_budget += trade.profit_loss  # NEW: update budget
                    # ...
```

---

## Summary & Key Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Entry Reference** | Use `anchor_price` | Consistent with existing TP calc |
| **Loss Calculation** | `% loss * total_invested` | Deterministic, matches capital accounting |
| **Execution Order** | DCA → SL → TP | Realistic market simulation |
| **Budget Impact** | Immediate deduction | Affects future trades realistically |
| **Disabled Behavior** | No-op (returns None/False) | Backward compatible |
| **Statistics Update** | Recalculate all metrics | Comprehensive analysis |
| **Edge Case: Both SL+TP** | SL executes first | Pessimistic (safer) |

---

## Financial Correctness Guarantees

1. **No phantom capital**: All capital accounted for (invested + available + realized losses)
2. **Deterministic outcomes**: Same config + data = same results
3. **Consistent ROI**: ROI = (final_budget - initial) / initial
4. **Proper loss tracking**: Losses reduce available capital for future trades
5. **Budget conservation**: ∑(profits) - ∑(losses) = change in available budget

---

## Example Walkthrough

```
CONFIG:
  initial_budget = $1,000
  stop_loss_percent = 10%
  dca_levels = [-2%, -4%, -6%]
  dca_allocations = [100, 200, 300]

BACKTEST FLOW:

1. Anchor = $100 (first candle high)
   available_budget = $1,000

2. Candle 5: Price drops to $98 (within -2% DCA)
   - Entry triggered
   - Fill DCA-1 @ $98
   - Stop-loss threshold = $100 * (1 - 0.10) = $90
   - Position: 100 coins @ $98 avg
   - total_invested = $100

3. Candle 10: Price touches $85 (goes below $90 threshold)
   - STOP-LOSS HIT
   - Exit price = $85
   - Loss % = (85 - 100) / 100 = -15%
   - Capital loss = 15% * $100 = $15
   - available_budget = $1,000 - $15 = $985
   - Trade record: profit_loss = -$15
   - Reset position, continue

4. Candle 20: New anchor = $102
   - Available capital for next trade = $985
   - DCA allocations use remaining budget
   - Cycle continues

FINAL RESULTS:
  Total trades: 8
  Winning: 5
  Stopped out: 2
  Total P&L: +$120
  Final budget: $1,120
  ROI: +12%
```
