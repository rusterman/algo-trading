# Stop-Loss Implementation Code Changes

## File-by-File Implementation Guide

This document provides exact code changes needed to implement stop-loss functionality.

---

## 1. config_loader.py - Add Stop-Loss Configuration

### Changes Needed:

1. **Add property to StrategyConfig class**:

```python
@property
def stop_loss_percent(self) -> float:
    """
    Get stop-loss percentage.
    
    Returns:
        float: Stop-loss percentage (0 = disabled, >0 = enabled)
                E.g., 10 means stop loss at -10% from entry
    """
    return self.config.get('stop_loss_percent', 0.0)
```

2. **Add validation in `_validate_config()` method**:

```python
def _validate_config(self):
    # ... existing validation code ...
    
    # Validate stop loss (NEW)
    stop_loss = self.config.get('stop_loss_percent', 0.0)
    if stop_loss < 0:
        raise ValueError("stop_loss_percent must be >= 0 (0 = disabled)")
    
    # Optional: warn if stop_loss >= 50% (too aggressive)
    if stop_loss >= 50:
        print(f"⚠️  WARNING: stop_loss_percent = {stop_loss}% is very aggressive")
```

3. **Update `print_config()` method** (if exists):

```python
def print_config(self):
    """Print configuration details"""
    # ... existing prints ...
    print(f"Stop Loss Percent:  {self.stop_loss_percent}% "
          f"({'DISABLED' if self.stop_loss_percent == 0 else 'ENABLED'})")
```

---

## 2. dca_strategy.py - Core Stop-Loss Implementation

### 2.1 Update Trade Dataclass

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
    
    # NEW: Stop-loss tracking fields
    stop_loss_triggered: bool = False
    stop_loss_price: Optional[float] = None
    stop_loss_loss: float = 0.0
    completion_reason: str = "take_profit"  # "take_profit" | "stop_loss"
```

### 2.2 Create BacktestResults Dataclass (NEW)

```python
@dataclass
class BacktestResults:
    """Comprehensive backtest statistics including stop-loss metrics"""
    initial_budget: float
    final_budget: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    stopped_out_trades: int  # Trades closed by stop-loss
    
    # Profit/Loss totals
    total_profit: float
    total_loss: float
    net_pnl: float
    
    # Percentages
    total_roi: float
    win_rate: float
    stop_loss_rate: float  # % of trades stopped
    avg_trade_pnl: float
    
    # Risk metrics
    largest_loss: float
    largest_profit: float
    avg_loss_magnitude: float
    avg_profit_magnitude: float
    
    # Duration
    avg_trade_duration_days: float
    total_test_days: float
```

### 2.3 Update DCAStrategy.__init__

```python
def __init__(
    self,
    initial_budget: float = 1000,
    budget_per_level: Optional[List[float]] = None,
    dca_levels: Optional[List[float]] = None,
    take_profit_percent: Optional[float] = None,
    stop_loss_percent: float = 0.0,  # NEW parameter
):
    """
    Initialize DCA strategy with optional stop-loss
    
    Args:
        initial_budget: Starting budget (default: $1000)
        budget_per_level: Optional custom budget allocation per level
        dca_levels: Optional custom DCA dump levels (negative percentages)
        take_profit_percent: Optional custom take-profit percentage
        stop_loss_percent: NEW - Stop-loss percentage (0 = disabled)
                          E.g., 10 means stop loss at -10% from entry
    """
    self.initial_budget = initial_budget
    self.stop_loss_percent = stop_loss_percent  # NEW
    self.dca_levels = dca_levels or self.DEFAULT_DCA_LEVELS
    self.take_profit_percent = (
        take_profit_percent
        if take_profit_percent is not None
        else self.DEFAULT_TAKE_PROFIT_PERCENT
    )
    
    # ... rest of existing init code ...
    
    # NEW: Track available capital
    self.available_budget = initial_budget
```

### 2.4 Add Stop-Loss Calculation Methods

```python
def calculate_stop_loss_threshold(self) -> Optional[float]:
    """
    Calculate the price threshold that triggers stop-loss.
    
    ONLY valid when:
    - stop_loss_percent > 0 (enabled)
    - At least one DCA level is filled
    
    Formula:
    - threshold = anchor_price * (1 - stop_loss_percent/100)
    
    Example:
    - anchor_price = $100
    - stop_loss_percent = 10
    - threshold = $100 * (1 - 0.10) = $90
    
    If price reaches $90 or below, stop-loss triggers.
    
    Returns:
        float: Stop-loss price threshold
        None: If stop-loss disabled or no position open
    """
    # Return None if stop-loss disabled
    if self.stop_loss_percent <= 0:
        return None
    
    # Only valid if in trade with at least one fill
    filled_levels = [lvl for lvl in self.active_dca_levels if lvl.filled]
    if not filled_levels:
        return None
    
    # Use anchor price as entry reference
    # (consistent with take-profit calculation)
    threshold = self.anchor_price * (1 - self.stop_loss_percent / 100)
    
    return threshold

def check_stop_loss_hit(self, candle_low: float) -> bool:
    """
    Check if stop-loss threshold was breached by candle wick.
    
    Execution rule: SL triggers if candle.low <= threshold
    
    Args:
        candle_low: Lowest price of current candle
        
    Returns:
        bool: True if stop-loss was triggered
    """
    threshold = self.calculate_stop_loss_threshold()
    
    # Return False if disabled or no threshold
    if threshold is None:
        return False
    
    # Trigger if wick touches or goes below threshold
    return candle_low <= threshold
```

### 2.5 Add Stop-Loss Close Method

```python
def close_trade_with_loss(
    self,
    exit_time: pd.Timestamp,
    loss_price: float,
    available_budget: float
) -> tuple[Trade, float]:
    """
    Close trade due to stop-loss being triggered.
    
    CRITICAL: Calculates actual capital loss and returns updated budget.
    
    Loss Calculation:
    - loss_pct = (loss_price - anchor_price) / anchor_price * 100
    - capital_loss = abs(loss_pct / 100) * total_invested
    - updated_budget = available_budget - capital_loss
    
    Example:
    - anchor_price = $100
    - loss_price = $85
    - total_invested = $1,000
    - loss_pct = (85-100)/100*100 = -15%
    - capital_loss = 0.15 * 1,000 = $150
    - updated_budget = 10,000 - 150 = 9,850
    
    Args:
        exit_time: pd.Timestamp - Timestamp of stop-loss execution
        loss_price: float - Price at which stop-loss executed
        available_budget: float - Current available capital before loss
        
    Returns:
        tuple[Trade, float]: (Trade object with loss record, updated_budget)
    """
    filled_levels = [lvl for lvl in self.active_dca_levels if lvl.filled]
    deepest_level = self.get_deepest_filled_level()
    
    # Calculate total invested capital
    total_invested = sum(lvl.budget_allocation for lvl in filled_levels)
    
    # Calculate unrealized loss percentage at stop price
    # loss_pct = (loss_price - entry_price) / entry_price * 100
    loss_pct = ((loss_price - self.anchor_price) / self.anchor_price) * 100
    
    # Calculate actual capital loss amount
    # capital_loss is always positive (represents dollars lost)
    capital_loss = abs(loss_pct / 100) * total_invested
    
    # Update available budget
    updated_budget = available_budget - capital_loss
    
    # Create trade record
    trade = Trade(
        start_time=self.trade_start_time,
        end_time=exit_time,
        anchor_price=self.anchor_price,
        deepest_level=deepest_level.level_num,
        deepest_price=deepest_level.fill_price,
        exit_price=loss_price,
        total_invested=total_invested,
        total_return=loss_price * sum(lvl.budget_allocation / lvl.fill_price 
                                      for lvl in filled_levels),
        profit_loss=-capital_loss,  # NEGATIVE: it's a loss
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

### 2.6 Update run_backtest() Method

```python
def run_backtest(self, df: pd.DataFrame) -> List[Trade]:
    """
    Run deterministic backtest on historical data with stop-loss support.
    
    MODIFIED ALGORITHM:
    1. Track anchor price (reference price P0)
    2. When candle.low <= P0 * (1 + first_dca_level), start trade
    3. For each candle in trade:
       a. Check DCA fills: if candle.low <= pi, fill level i
       b. ★ Check STOP-LOSS: if candle.low <= threshold, close with loss
       c. Check TP: if candle.high >= tp_price, close with profit
    4. After close, reset position and start new anchor
    5. Track available_budget throughout
    
    KEY CHANGES:
    - ★ Stop-loss check BEFORE take-profit (line execution order)
    - ★ available_budget tracking and updates
    - ★ Proper capital loss accounting
    
    Args:
        df: DataFrame with columns: datetime, high, low
        
    Returns:
        List of completed Trade objects
    """
    self.reset_game()
    self.completed_trades = []
    self.available_budget = self.initial_budget  # NEW: reset available capital
    
    for idx, row in df.iterrows():
        timestamp = row['datetime']
        candle_high = row['high']
        candle_low = row['low']
        
        if not self.in_trade:
            # NOT IN TRADE - Looking for entry trigger
            if self.anchor_price is None:
                # First candle becomes anchor (P0)
                self.anchor_price = candle_high
                continue
            
            # Check if price dumped to first DCA level or beyond
            dump_from_anchor = ((candle_low - self.anchor_price) / self.anchor_price) * 100
            
            if dump_from_anchor <= self.dca_levels[0]:  # e.g., -6%
                # Start new trade
                self.in_trade = True
                self.trade_start_time = timestamp
                # Calculate all DCA entry prices: pi = P0 * (1 + di)
                self.active_dca_levels = self.calculate_dca_prices(self.anchor_price)
                
                # Check fills on this candle
                self.check_dca_fills(candle_low)
            else:
                # Update anchor to current high if no dump yet
                self.anchor_price = max(self.anchor_price, candle_high)
        
        else:
            # IN TRADE - Check for events in order
            
            # STEP 1: Check DCA fills (price going down touches low)
            newly_filled = self.check_dca_fills(candle_low)
            
            # STEP 2: ★ Check STOP-LOSS (NEW - before TP)
            # If stop-loss is hit, close trade and skip TP check
            if self.check_stop_loss_hit(candle_low):
                sl_threshold = self.calculate_stop_loss_threshold()
                # Exit at stop-loss threshold price
                trade, self.available_budget = self.close_trade_with_loss(
                    timestamp,
                    sl_threshold,
                    self.available_budget  # NEW: pass current available capital
                )
                
                # Reset and start looking for next trade
                self.reset_game()
                self.anchor_price = candle_high
                continue  # Skip TP check for this candle
            
            # STEP 3: Check TAKE-PROFIT
            # (only if not stopped out)
            if self.check_take_profit_hit(candle_high):
                tp_price = self.calculate_take_profit_price()
                trade = self.close_trade(timestamp, tp_price)
                
                # NEW: Update available budget with profit
                self.available_budget += trade.profit_loss
                
                # Reset and start looking for next trade
                # Position resets completely after TP
                self.reset_game()
                self.anchor_price = candle_high  # New anchor after trade closes
    
    return self.completed_trades
```

### 2.7 Add Results Calculation Function (NEW)

```python
def calculate_backtest_results(self) -> BacktestResults:
    """
    Calculate comprehensive backtest statistics.
    
    Recalculates ALL metrics considering stop-loss impact:
    - Available budget affected by losses
    - Win/loss/stop-out counts
    - Profit/loss totals
    - ROI and rates
    - Risk metrics
    
    Returns:
        BacktestResults object with all statistics
    """
    trades = self.completed_trades
    
    # Handle empty trades case
    if not trades:
        return BacktestResults(
            initial_budget=self.initial_budget,
            final_budget=self.initial_budget,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            stopped_out_trades=0,
            total_profit=0.0,
            total_loss=0.0,
            net_pnl=0.0,
            total_roi=0.0,
            win_rate=0.0,
            stop_loss_rate=0.0,
            avg_trade_pnl=0.0,
            largest_loss=0.0,
            largest_profit=0.0,
            avg_loss_magnitude=0.0,
            avg_profit_magnitude=0.0,
            avg_trade_duration_days=0.0,
            total_test_days=0.0
        )
    
    # Separate trades by outcome
    winning_trades = [t for t in trades if t.profit_loss > 0]
    losing_trades = [t for t in trades if t.profit_loss < 0]
    stopped_out_trades = [t for t in trades if t.stop_loss_triggered]
    
    # Profit/Loss totals
    total_profit = sum(t.profit_loss for t in winning_trades)
    total_loss = abs(sum(t.profit_loss for t in losing_trades))
    net_pnl = sum(t.profit_loss for t in trades)
    
    # Final budget = initial + all P&L
    final_budget = self.initial_budget + net_pnl
    
    # ROI = (final - initial) / initial * 100
    total_roi = ((final_budget - self.initial_budget) / self.initial_budget * 100) \
        if self.initial_budget > 0 else 0.0
    
    # Counts and rates
    total_trades = len(trades)
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0.0
    stop_loss_rate = (len(stopped_out_trades) / total_trades * 100) if total_trades > 0 else 0.0
    
    # Averages
    avg_trade_pnl = net_pnl / total_trades if total_trades > 0 else 0.0
    avg_loss_magnitude = total_loss / len(losing_trades) if losing_trades else 0.0
    avg_profit_magnitude = total_profit / len(winning_trades) if winning_trades else 0.0
    
    # Extremes
    largest_loss = min(t.profit_loss for t in trades) if trades else 0.0
    largest_profit = max(t.profit_loss for t in trades) if trades else 0.0
    
    # Duration metrics
    durations_days = [(t.end_time - t.start_time).total_seconds() / (24 * 3600) 
                      for t in trades]
    avg_trade_duration_days = sum(durations_days) / len(durations_days) if durations_days else 0.0
    
    if trades:
        total_test_days = (trades[-1].end_time - trades[0].start_time).total_seconds() / (24 * 3600)
    else:
        total_test_days = 0.0
    
    return BacktestResults(
        initial_budget=self.initial_budget,
        final_budget=final_budget,
        total_trades=total_trades,
        winning_trades=len(winning_trades),
        losing_trades=len(losing_trades),
        stopped_out_trades=len(stopped_out_trades),
        total_profit=total_profit,
        total_loss=total_loss,
        net_pnl=net_pnl,
        total_roi=total_roi,
        win_rate=win_rate,
        stop_loss_rate=stop_loss_rate,
        avg_trade_pnl=avg_trade_pnl,
        largest_loss=largest_loss,
        largest_profit=largest_profit,
        avg_loss_magnitude=avg_loss_magnitude,
        avg_profit_magnitude=avg_profit_magnitude,
        avg_trade_duration_days=avg_trade_duration_days,
        total_test_days=total_test_days
    )
```

### 2.8 Update print_backtest_results() Method

```python
def print_backtest_results(self):
    """Print comprehensive backtest results with stop-loss metrics."""
    
    results = self.calculate_backtest_results()
    
    if not self.completed_trades:
        print("\nNo completed trades found.")
        return
    
    print(f"\n{'='*70}")
    print(f"BACKTEST RESULTS - DCA STRATEGY")
    print(f"{'='*70}")
    print(f"Initial Budget:     ${results.initial_budget:,.2f}")
    print(f"Final Budget:       ${results.final_budget:,.2f}")
    print(f"Total P&L:          ${results.net_pnl:,.2f}")
    print(f"ROI:                {results.total_roi:+.2f}%")
    
    print(f"\n{'Trade Summary':^70}")
    print(f"{'-'*70}")
    print(f"Total Trades:       {results.total_trades}")
    print(f"  Winning:          {results.winning_trades} ({results.win_rate:.1f}%)")
    print(f"  Losing:           {results.losing_trades} ({100-results.win_rate:.1f}%)")
    print(f"  Stopped Out:      {results.stopped_out_trades} ({results.stop_loss_rate:.1f}%)")
    
    print(f"\n{'Profit & Loss':^70}")
    print(f"{'-'*70}")
    print(f"Total Profit:       ${results.total_profit:,.2f}")
    print(f"Total Loss:         -${results.total_loss:,.2f}")
    print(f"Avg Trade P&L:      ${results.avg_trade_pnl:,.2f}")
    
    if results.winning_trades > 0:
        print(f"Avg Win:            ${results.avg_profit_magnitude:,.2f}")
    if results.losing_trades > 0:
        print(f"Avg Loss:           -${results.avg_loss_magnitude:,.2f}")
    
    print(f"Largest Profit:     ${results.largest_profit:,.2f}")
    print(f"Largest Loss:       ${results.largest_loss:,.2f}")
    
    print(f"\n{'Duration':^70}")
    print(f"{'-'*70}")
    print(f"Avg Trade Duration: {results.avg_trade_duration_days:.2f} days")
    print(f"Total Test Period:  {results.total_test_days:.2f} days")
    
    # Print stop-loss info if enabled
    if self.stop_loss_percent > 0:
        print(f"\n{'Stop-Loss (Enabled)':^70}")
        print(f"{'-'*70}")
        print(f"Stop-Loss %:        {self.stop_loss_percent}%")
        print(f"Stopped Out:        {results.stopped_out_trades} trades")
        total_sl_loss = sum(t.stop_loss_loss for t in self.completed_trades 
                           if t.stop_loss_triggered)
        print(f"Total SL Loss:      -${total_sl_loss:,.2f}")
    else:
        print(f"\n{'Stop-Loss (Disabled)':^70}")
    
    # Print individual trades
    print(f"\n{'='*70}")
    print(f"TRADE DETAILS")
    print(f"{'='*70}")
    for i, trade in enumerate(self.completed_trades, 1):
        self._print_trade_details(i, trade)

def _print_trade_details(self, trade_num: int, trade: Trade):
    """Print details for a single trade"""
    duration = trade.end_time - trade.start_time
    duration_days = duration.total_seconds() / (24 * 3600)
    
    completion_status = "🛑 STOP-LOSS" if trade.stop_loss_triggered else "✓ TAKE-PROFIT"
    profit_color = "📈" if trade.profit_loss > 0 else "📉"
    
    print(f"\n{'─'*70}")
    print(f"Trade #{trade_num} - {completion_status}")
    print(f"{'─'*70}")
    print(f"Period:             {trade.start_time} → {trade.end_time}")
    print(f"Duration:           {duration_days:.2f} days")
    print(f"Anchor Price:       ${trade.anchor_price:,.2f}")
    print(f"Deepest Level:      DCA-{trade.deepest_level} (${trade.deepest_price:,.2f})")
    print(f"DCA Levels Filled:  {trade.dca_levels_filled}")
    print(f"Total Invested:     ${trade.total_invested:,.2f}")
    print(f"Exit Price:         ${trade.exit_price:,.2f}")
    print(f"Result:             {profit_color} ${trade.profit_loss:,.2f} ({trade.profit_percent:+.2f}%)")
    
    if trade.stop_loss_triggered:
        print(f"Stop-Loss Price:    ${trade.stop_loss_price:,.2f}")
        print(f"SL Loss Amount:     -${trade.stop_loss_loss:,.2f}")
```

---

## 3. run_backtest.py - Update Entry Point

### Add stop_loss_percent to strategy initialization:

```python
def run_backtest_from_config(config_file="strategy_config.json"):
    """
    Run DCA backtest using configuration file
    """
    # Load configuration
    print("Loading configuration...")
    config = load_config(config_file)
    config.print_config()
    
    # Load data
    df = load_and_prepare_data(config.csv_file)
    
    # Filter by date range if specified
    if config.start_date:
        start = pd.to_datetime(config.start_date)
        df = df[df['datetime'] >= start]
        print(f"Filtered to start date: {start}")
    
    if config.end_date:
        end = pd.to_datetime(config.end_date)
        df = df[df['datetime'] <= end]
        print(f"Filtered to end date: {end}")
    
    print(f"\nBacktest data: {len(df)} candles")
    print(f"Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # Create strategy with config parameters
    print(f"\nInitializing strategy...")
    strategy = DCAStrategy(
        initial_budget=config.initial_budget,
        budget_per_level=config.budget_allocation,
        dca_levels=config.dca_levels,
        take_profit_percent=config.take_profit_percent,
        stop_loss_percent=config.stop_loss_percent,  # NEW parameter
    )
    
    # Run backtest
    print(f"\nRunning backtest...")
    trades = strategy.run_backtest(df)
    
    # Print results
    strategy.print_backtest_results()
    
    return strategy, trades
```

---

## 4. strategy_config.json - Add Parameter

```json
{
  "csv_file": "data/sol_15m_data_2020_to_2025.csv",
  "start_date": "2025-01-01",
  "end_date": "2026-01-01",
  "initial_budget": 8000,
  "stop_loss_percent": 10.0,
  "dca_levels": [-2, -4, -8, -12, -16, -20, -24, -28],
  "dca_allocations": [30, 60, 120, 240, 480, 960, 1920, 3840],
  "take_profit_percent": 5.0
}
```

---

## Testing Checklist

### Unit Tests (add to test file):

```python
def test_stop_loss_disabled():
    """When stop_loss_percent=0, stop-loss should not trigger"""
    strategy = DCAStrategy(
        initial_budget=1000,
        stop_loss_percent=0.0  # DISABLED
    )
    strategy.anchor_price = 100
    strategy.active_dca_levels = strategy.calculate_dca_prices(100)
    strategy.active_dca_levels[0].filled = True
    
    # Even with extreme drop, should not trigger
    assert strategy.check_stop_loss_hit(50) == False
    assert strategy.calculate_stop_loss_threshold() is None

def test_stop_loss_enabled():
    """When stop_loss_percent>0, stop-loss should trigger at threshold"""
    strategy = DCAStrategy(
        initial_budget=1000,
        stop_loss_percent=10.0  # 10% stop loss
    )
    strategy.anchor_price = 100
    strategy.active_dca_levels = strategy.calculate_dca_prices(100)
    strategy.active_dca_levels[0].filled = True
    
    # Should trigger at or below 90
    assert strategy.check_stop_loss_hit(90) == True
    assert strategy.check_stop_loss_hit(89) == True
    assert strategy.check_stop_loss_hit(91) == False
    
    # Threshold should be exactly 90
    assert strategy.calculate_stop_loss_threshold() == 90.0

def test_stop_loss_capital_loss():
    """Stop-loss should properly reduce available budget"""
    strategy = DCAStrategy(
        initial_budget=1000,
        stop_loss_percent=10.0,
        budget_per_level=[100]
    )
    strategy.in_trade = True
    strategy.trade_start_time = pd.Timestamp('2025-01-01')
    strategy.anchor_price = 100
    
    # Create a filled level
    level = DCALevel(1, -5, 95, 100, True, 95)
    strategy.active_dca_levels = [level]
    
    # Close with loss
    trade, new_budget = strategy.close_trade_with_loss(
        pd.Timestamp('2025-01-02'),
        85,  # Lost 15%
        1000
    )
    
    # Should lose 15% of 100 = 15 dollars
    assert trade.profit_loss == -15.0
    assert new_budget == 985.0

def test_backward_compatibility():
    """Existing code without stop_loss should work unchanged"""
    strategy = DCAStrategy(
        initial_budget=1000,
        dca_levels=[-6, -9, -12]
        # stop_loss_percent NOT provided, defaults to 0
    )
    
    assert strategy.stop_loss_percent == 0.0
    assert strategy.calculate_stop_loss_threshold() is None
```

---

## Verification Steps

1. **Configuration loads correctly**:
   ```bash
   python -c "from config_loader import load_config; c = load_config('strategy_config.json'); print(f'SL: {c.stop_loss_percent}')"
   ```

2. **Backtest runs without errors**:
   ```bash
   python run_backtest.py
   ```

3. **Output shows stop-loss metrics** when enabled
4. **Backward compatible** - backtest with `stop_loss_percent: 0` produces identical results
5. **Budget accounting is consistent** - final_budget = initial + all P&L
