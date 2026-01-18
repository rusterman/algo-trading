"""
Visualize OHLCV data with candlestick charts (TradingView-like)
"""
import pandas as pd
import mplfinance as mpf
import sys
from pathlib import Path


def plot_candlesticks(csv_file, num_candles=500, style='yahoo'):
    """
    Plot candlestick chart from OHLCV data
    
    Args:
        csv_file: Path to CSV file
        num_candles: Number of recent candles to display (default: 500)
        style: Chart style ('yahoo', 'charles', 'nightclouds', 'sas', 'default')
    """
    # Load data
    print(f"Loading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Standardize column names
    df.columns = df.columns.str.strip().str.lower()
    
    # Set datetime index
    if 'open time' in df.columns:
        df['datetime'] = pd.to_datetime(df['open time'])
    elif 'timestamp' in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'])
    else:
        print("Error: No timestamp column found")
        print(f"Available columns: {list(df.columns)}")
        return
    
    # Remove rows with invalid timestamps
    df = df.dropna(subset=['datetime'])
    df.set_index('datetime', inplace=True)
    
    # Select required columns for mplfinance (must be named exactly: Open, High, Low, Close, Volume)
    plot_df = pd.DataFrame({
        'Open': df['open'],
        'High': df['high'],
        'Low': df['low'],
        'Close': df['close'],
        'Volume': df['volume']
    })
    
    # Take last N candles
    plot_df = plot_df.tail(num_candles)
    
    print(f"Plotting {len(plot_df)} candles...")
    print(f"Date range: {plot_df.index[0]} to {plot_df.index[-1]}")
    
    # Create the plot
    mpf.plot(
        plot_df,
        type='candle',
        style=style,
        volume=True,
        title=f'{Path(csv_file).stem}',
        ylabel='Price',
        ylabel_lower='Volume',
        figsize=(16, 9),
        warn_too_much_data=1000
    )


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python view_chart.py data/btc_15m_data_2018_to_2025.csv")
        print("  python view_chart.py data/btc_15m_data_2018_to_2025.csv 1000")
        print("  python view_chart.py data/btc_15m_data_2018_to_2025.csv 500 nightclouds")
        print("\nAvailable styles: yahoo, charles, nightclouds, sas, default")
        return
    
    csv_file = sys.argv[1]
    num_candles = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    style = sys.argv[3] if len(sys.argv) > 3 else 'yahoo'
    
    plot_candlesticks(csv_file, num_candles, style)


if __name__ == '__main__':
    main()
