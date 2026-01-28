"""
DCA (Dollar Cost Averaging) Strategy Implementation

DETERMINISTIC BACKTEST ALGORITHM - PORTFOLIO-LEVEL TAKE-PROFIT

Strategy Overview:
- Multi-level DCA with fixed USD allocations per level
- Portfolio-level profit calculation (NOT price-from-last-entry)
- Spot-only, no leverage
- Deterministic execution

Key Variables:
- P0 = reference/anchor price
- di = dump percentage for level i (e.g., -6%, -9%)
- ai = USD allocation for level i
- pi = execution price = P0 * (1 + di/100)
- qi = quantity bought = ai / pi

Position State (maintained continuously):
- A = sum(ai)        # total invested capital
- Q = sum(qi)        # total position size
- avg_price = A / Q  # weighted average entry price

Profit Calculation (CRITICAL):
- Unrealized PnL at market price P:
  pnl = Q * P - A
  pnl_pct = pnl / A

Take-Profit Condition:
- TP triggers when: pnl_pct >= target_profit (5%)
- Equivalent: P >= avg_price * (1 + target_profit)
- ✓ Portfolio-level profit (correct)
- ✗ NOT: price >= last_dca_price * 1.05 (incorrect)

Candle Handling:
- DCA entry: candle.low <= pi
- Take profit: candle.high >= tp_price
- DCA levels executed in order, never skipped
- After TP, position resets completely

Strategy operates on fixed timeframe with predefined DCA levels.
Uses only candle wicks (high/low), ignoring bodies (open/close).
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


@dataclass
class DCALevel:
    """Represents a single DCA level"""
    level_num: int          # 1-6
    dump_percent: float     # -6%, -9%, etc.
    entry_price: float      # Calculated entry price
    budget_allocation: float  # Fixed budget for this level
    filled: bool = False    # Whether this level was filled
    fill_price: Optional[float] = None  # Actual fill price
    

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


class DCAStrategy:
    """
    DCA Strategy with fixed dump levels and take-profit target
    
    Key features:
    - Static DCA levels: -6%, -9%, -12%, -16%, -20%, -24%
    - Uses only candle wicks (high/low)
    - Fixed budget allocation per level
    - Take profit at +5% from deepest DCA level
    - Restarts after each complete trade
    """
    
    # Static DCA dump levels (negative percentages)
    DCA_LEVELS = [-6, -9, -12, -16, -20, -24]
    
    # Take profit target (positive percentage from deepest level)
    TAKE_PROFIT_PERCENT = 5.0
    
    def __init__(self, initial_budget: float = 1000, budget_per_level: Optional[List[float]] = None):
        """
        Initialize DCA strategy
        
        Args:
            initial_budget: Starting budget (default: $1000)
            budget_per_level: Optional custom budget allocation per level
                            If None, uses equal distribution
        """
        self.initial_budget = initial_budget
        
        # Default equal budget allocation across 6 levels
        if budget_per_level is None:
            self.budget_per_level = [initial_budget / 6] * 6
        else:
            if len(budget_per_level) != 6:
                raise ValueError("Must provide exactly 6 budget allocations")
            self.budget_per_level = budget_per_level
        
        # Strategy state
        self.in_trade = False
        self.anchor_price = None
        self.trade_start_time = None
        self.active_dca_levels: List[DCALevel] = []
        self.completed_trades: List[Trade] = []
        
    def reset_game(self):
        """Reset strategy state for new trade cycle"""
        self.in_trade = False
        self.anchor_price = None
        self.trade_start_time = None
        self.active_dca_levels = []
        
    def calculate_dca_prices(self, anchor_price: float) -> List[DCALevel]:
        """
        Calculate DCA entry prices from anchor price
        
        Args:
            anchor_price: Current price that becomes the anchor
            
        Returns:
            List of DCALevel objects with calculated entry prices
        """
        dca_levels = []
        for i, dump_pct in enumerate(self.DCA_LEVELS, start=1):
            entry_price = anchor_price * (1 + dump_pct / 100)
            dca_levels.append(DCALevel(
                level_num=i,
                dump_percent=dump_pct,
                entry_price=entry_price,
                budget_allocation=self.budget_per_level[i-1]
            ))
        return dca_levels
    
    def check_dca_fills(self, candle_low: float) -> List[DCALevel]:
        """
        Check which DCA levels were filled by candle low (wick touch)
        
        Execution rule: DCA entry triggers if candle.low <= pi
        Levels are executed in order, never skipped.
        
        Args:
            candle_low: Low price of current candle
            
        Returns:
            List of newly filled DCA levels
        """
        newly_filled = []
        for level in self.active_dca_levels:
            if not level.filled and candle_low <= level.entry_price:
                level.filled = True
                level.fill_price = level.entry_price  # Filled at limit price
                newly_filled.append(level)
        return newly_filled
    
    def get_deepest_filled_level(self) -> Optional[DCALevel]:
        """Get the deepest (lowest price) filled DCA level"""
        filled_levels = [lvl for lvl in self.active_dca_levels if lvl.filled]
        if not filled_levels:
            return None
        return max(filled_levels, key=lambda x: x.level_num)
    
    def calculate_take_profit_price(self) -> Optional[float]:
        """
        Calculate take-profit price that guarantees target profit on total position
        
        PORTFOLIO-LEVEL PROFIT CALCULATION:
        - A = sum(ai) = total invested capital
        - Q = sum(qi) = total position size (coins)
        - avg_price = A / Q = weighted average entry price
        
        Take-profit condition:
        - pnl_pct = (Q * P - A) / A >= target_profit
        - Solving for P: P >= (1 + target_profit) * A / Q
        - Therefore: tp_price = (1 + target_profit) * avg_price
        
        This ensures PORTFOLIO profit = target_profit, not just price movement.
        
        Returns:
            Take-profit price or None if no levels filled
        """
        filled_levels = [lvl for lvl in self.active_dca_levels if lvl.filled]
        if not filled_levels:
            return None
        
        # Calculate position state variables
        # A = total invested capital
        total_invested = sum(lvl.budget_allocation for lvl in filled_levels)
        # Q = total position size (coins)
        total_coins = sum(lvl.budget_allocation / lvl.fill_price for lvl in filled_levels)
        
        # avg_price = A / Q
        avg_price = total_invested / total_coins
        
        # tp_price = avg_price * (1 + target_profit)
        # Equivalent to: (1 + target_profit) * A / Q
        tp_price = avg_price * (1 + self.TAKE_PROFIT_PERCENT / 100)
        
        return tp_price
    
    def check_take_profit_hit(self, candle_high: float) -> bool:
        """
        Check if take-profit level was hit by candle high (wick touch)
        
        Execution rule: TP triggers if candle.high >= tp_price
        where tp_price guarantees portfolio-level target profit.
        
        Args:
            candle_high: High price of current candle
            
        Returns:
            True if take-profit was hit
        """
        tp_price = self.calculate_take_profit_price()
        if tp_price is None:
            return False
        return candle_high >= tp_price
    
    def close_trade(self, exit_time: pd.Timestamp, exit_price: float) -> Trade:
        """
        Close current trade and calculate final results
        
        Position state at close:
        - A = total invested capital
        - Q = total position size
        - P = exit price (take-profit price)
        
        Profit calculation:
        - total_return = Q * P
        - pnl = total_return - A = Q * P - A
        - pnl_pct = pnl / A
        
        Args:
            exit_time: Timestamp of exit
            exit_price: Price at exit (take-profit price)
            
        Returns:
            Trade object with complete trade information
        """
        deepest_level = self.get_deepest_filled_level()
        filled_levels = [lvl for lvl in self.active_dca_levels if lvl.filled]
        
        # Calculate position state: A (total invested) and Q (total coins)
        total_invested = sum(lvl.budget_allocation for lvl in filled_levels)  # A
        total_coins = sum(lvl.budget_allocation / lvl.fill_price for lvl in filled_levels)  # Q
        
        # Calculate return: total_return = Q * P
        total_return = total_coins * exit_price
        
        # Calculate profit: pnl = Q * P - A
        profit_loss = total_return - total_invested
        
        # Calculate profit percentage: pnl_pct = pnl / A
        profit_percent = (profit_loss / total_invested) * 100 if total_invested > 0 else 0
        
        trade = Trade(
            start_time=self.trade_start_time,
            end_time=exit_time,
            anchor_price=self.anchor_price,
            deepest_level=deepest_level.level_num,
            deepest_price=deepest_level.fill_price,
            exit_price=exit_price,
            total_invested=total_invested,
            total_return=total_return,
            profit_loss=profit_loss,
            profit_percent=profit_percent,
            dca_levels_filled=[lvl.level_num for lvl in filled_levels]
        )
        
        self.completed_trades.append(trade)
        return trade
    
    def run_backtest(self, df: pd.DataFrame) -> List[Trade]:
        """
        Run deterministic backtest on historical data
        
        ALGORITHM STEPS:
        1. Track anchor price (reference price P0)
        2. When candle.low <= P0 * (1 + first_dca_level), start trade
        3. For each candle in trade:
           - Check DCA fills: if candle.low <= pi, fill level i
           - Check TP: if candle.high >= tp_price, close trade
        4. After TP, reset position completely and start new anchor
        
        CONSTRAINTS:
        - Spot trading only, no leverage
        - DCA levels executed in order, never skipped
        - Portfolio-level profit calculation
        - Deterministic execution (no randomness)
        
        Args:
            df: DataFrame with columns: datetime, high, low
               (only wicks are used, open/close ignored)
               
        Returns:
            List of completed Trade objects
        """
        self.reset_game()
        self.completed_trades = []
        
        for idx, row in df.iterrows():
            timestamp = row['datetime']
            candle_high = row['high']
            candle_low = row['low']
            
            if not self.in_trade:
                # Not in trade - looking for entry trigger
                if self.anchor_price is None:
                    # First candle becomes anchor (P0)
                    self.anchor_price = candle_high
                    continue
                
                # Check if price dumped to first DCA level or beyond
                dump_from_anchor = ((candle_low - self.anchor_price) / self.anchor_price) * 100
                
                if dump_from_anchor <= self.DCA_LEVELS[0]:  # e.g., -6%
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
                # In trade - check for DCA fills and take-profit
                
                # CRITICAL INTRA-CANDLE ORDER:
                # 1. First check DCA fills (price going down touches low)
                # 2. Then check TP (price going up touches high) with UPDATED position
                # This ensures new fills affect the TP calculation before TP check
                
                # First check for new DCA fills (order: candle.low <= pi)
                newly_filled = self.check_dca_fills(candle_low)
                
                # Then check if take-profit was hit (order: candle.high >= tp_price)
                # TP price is calculated with ALL fills up to this point
                if self.check_take_profit_hit(candle_high):
                    tp_price = self.calculate_take_profit_price()
                    trade = self.close_trade(timestamp, tp_price)
                    
                    # Reset and start looking for next trade
                    # Position resets completely after TP
                    self.reset_game()
                    self.anchor_price = candle_high  # New anchor after trade closes
        
        return self.completed_trades
    
    def print_trade_summary(self, trade: Trade):
        """Print summary of a single trade"""
        # Calculate duration
        duration = trade.end_time - trade.start_time
        duration_days = duration.total_seconds() / (24 * 3600)
        duration_hours = duration.total_seconds() / 3600
        
        # Format duration
        if duration_days >= 1:
            duration_str = f"{duration_days:.2f} days ({duration})"
        else:
            duration_str = f"{duration_hours:.2f} hours ({duration})"
        
        print(f"\n{'='*70}")
        print(f"Trade: {trade.start_time} → {trade.end_time}")
        print(f"{'='*70}")
        print(f"Duration:           {duration_str}")
        print(f"Anchor Price:       ${trade.anchor_price:,.2f}")
        print(f"Deepest Level:      DCA-{trade.deepest_level} (${trade.deepest_price:,.2f})")
        print(f"Levels Filled:      {trade.dca_levels_filled}")
        print(f"Exit Price:         ${trade.exit_price:,.2f}")
        print(f"Total Invested:     ${trade.total_invested:,.2f}")
        print(f"Total Return:       ${trade.total_return:,.2f}")
        print(f"Profit/Loss:        ${trade.profit_loss:,.2f} ({trade.profit_percent:+.2f}%)")
        
    def print_backtest_results(self):
        """Print comprehensive backtest results"""
        if not self.completed_trades:
            print("\nNo completed trades found.")
            return
        
        print(f"\n{'='*70}")
        print(f"BACKTEST RESULTS - DCA STRATEGY")
        print(f"{'='*70}")
        print(f"Total Trades:       {len(self.completed_trades)}")
        
        # Calculate aggregate statistics
        total_profit = sum(t.profit_loss for t in self.completed_trades)
        winning_trades = [t for t in self.completed_trades if t.profit_loss > 0]
        losing_trades = [t for t in self.completed_trades if t.profit_loss <= 0]
        
        # Calculate average trade duration
        durations = [(t.end_time - t.start_time).total_seconds() / (24 * 3600) for t in self.completed_trades]
        avg_duration_days = np.mean(durations)
        min_duration_days = np.min(durations)
        max_duration_days = np.max(durations)
        
        print(f"Winning Trades:     {len(winning_trades)} ({len(winning_trades)/len(self.completed_trades)*100:.1f}%)")
        print(f"Losing Trades:      {len(losing_trades)} ({len(losing_trades)/len(self.completed_trades)*100:.1f}%)")
        print(f"Total Profit/Loss:  ${total_profit:,.2f}")
        print(f"Avg Trade Duration: {avg_duration_days:.2f} days")
        print(f"Min/Max Duration:   {min_duration_days:.2f} / {max_duration_days:.2f} days")
        
        if winning_trades:
            avg_win = np.mean([t.profit_loss for t in winning_trades])
            print(f"Average Win:        ${avg_win:,.2f}")
        
        if losing_trades:
            avg_loss = np.mean([t.profit_loss for t in losing_trades])
            print(f"Average Loss:       ${avg_loss:,.2f}")
        
        # Show each trade
        for trade in self.completed_trades:
            self.print_trade_summary(trade)


def load_and_prepare_data(csv_file: str) -> pd.DataFrame:
    """
    Load CSV data and prepare for strategy
    
    Args:
        csv_file: Path to CSV file
        
    Returns:
        DataFrame with datetime, high, low columns
    """
    print(f"Loading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Standardize column names
    df.columns = df.columns.str.strip().str.lower()
    
    # Set datetime
    if 'open time' in df.columns:
        df['datetime'] = pd.to_datetime(df['open time'])
    elif 'timestamp' in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'])
    else:
        raise ValueError("No timestamp column found")
    
    # Ensure datetime is timezone-naive (no conversion)
    if df['datetime'].dt.tz is not None:
        df['datetime'] = df['datetime'].dt.tz_localize(None)
    
    df = df.dropna(subset=['datetime'])
    
    # Only need datetime, high, low (wicks only)
    df = df[['datetime', 'high', 'low']].copy()
    
    print(f"Loaded {len(df)} candles")
    print(f"Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    return df


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 dca_strategy.py data/btc_15m_data_2018_to_2025.csv")
        print("  python3 dca_strategy.py data/btc_1h_data_2018_to_2025.csv 5000")
        print("\nArguments:")
        print("  csv_file      Path to CSV file with OHLC data")
        print("  budget        Initial budget (default: 1000)")
        print("\nStrategy Parameters:")
        print("  DCA Levels:   -6%, -9%, -12%, -16%, -20%, -24%")
        print("  Take Profit:  +5% from deepest filled level")
        print("  Uses:         Only candle wicks (high/low)")
        return
    
    csv_file = sys.argv[1]
    initial_budget = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
    
    # Load data
    df = load_and_prepare_data(csv_file)
    
    # Initialize strategy
    strategy = DCAStrategy(initial_budget=initial_budget)
    
    print(f"\nRunning DCA Strategy Backtest...")
    print(f"Initial Budget: ${initial_budget:,.2f}")
    print(f"DCA Levels: {strategy.DCA_LEVELS}")
    print(f"Take Profit: +{strategy.TAKE_PROFIT_PERCENT}%")
    
    # Run backtest
    trades = strategy.run_backtest(df)
    
    # Print results
    strategy.print_backtest_results()


if __name__ == '__main__':
    main()