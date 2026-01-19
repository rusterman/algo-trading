"""
Interactive chart viewer using Plotly (TradingView-like experience)
Much better interactivity than matplotlib - hover to see values, zoom, pan
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path


def plot_interactive_chart(csv_file, num_candles=1000, show_volume=True):
    """
    Plot interactive candlestick chart with volume
    
    Args:
        csv_file: Path to CSV file
        num_candles: Number of recent candles to display (default: 1000)
        show_volume: Whether to show volume panel (default: True)
    """
    # Load data
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
        print("Error: No timestamp column found")
        return
    
    df = df.dropna(subset=['datetime'])
    
    # Take last N candles
    df = df.tail(num_candles)
    
    print(f"Plotting {len(df)} candles...")
    print(f"Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # Determine subplot configuration
    num_rows = 1  # Price is always shown
    row_heights = []
    subplot_titles = ['Price']
    
    if show_volume:
        num_rows += 1
        subplot_titles.append('Volume')
    
    # Calculate row heights
    if num_rows == 1:
        row_heights = [1.0]
    else:  # 2 rows
        row_heights = [0.7, 0.3]
    
    # Create subplots
    if show_volume:
        print("✓ Volume panel enabled")
        
    fig = make_subplots(
        rows=num_rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=subplot_titles
    )
    
    # Add candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df['datetime'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='OHLC',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350'
        ),
        row=1, col=1
    )
    
    # Track current row for subplots
    current_row = 2
    
    # Add volume bars if enabled
    if show_volume:
        colors = ['#26a69a' if close >= open else '#ef5350' 
                  for close, open in zip(df['close'], df['open'])]
        
        fig.add_trace(
            go.Bar(
                x=df['datetime'],
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                showlegend=False
            ),
            row=current_row, col=1
        )
        fig.update_yaxes(title_text="Volume", row=current_row, col=1)
        current_row += 1
    
    # Calculate chart height based on panels
    chart_height = 400 + (300 * num_rows)
    
    # Update layout
    fig.update_layout(
        title=f'{Path(csv_file).stem}',
        xaxis_rangeslider_visible=False,
        height=chart_height,
        template='plotly_dark',
        hovermode='x unified',
        showlegend=True
    )
    
    # Update axes
    fig.update_xaxes(title_text="Date", row=num_rows, col=1)
    fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
    
    print("\n✓ Opening interactive chart in browser...")
    print("  • Hover over candles to see values")
    print("  • Click and drag to zoom")
    print("  • Double-click to reset zoom")
    print("  • Use toolbar for more options")
    
    # Show the plot
    fig.show()


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python view_chart_interactive.py data/btc_15m_data_2018_to_2025.csv")
        print("  python view_chart_interactive.py data/btc_15m_data_2018_to_2025.csv 2000")
        print("  python view_chart_interactive.py data/btc_15m_data.csv 1000 --no-volume")
        print("\nOptions:")
        print("  --no-volume    Hide volume panel")
        print("\nInteractive features:")
        print("  - Hover to see exact values")
        print("  - Click and drag to zoom into specific areas")
        print("  - Double-click to reset")
        print("  - Pan by holding Shift and dragging")
        return
    
    csv_file = sys.argv[1]
    num_candles = 1000
    show_volume = True
    
    # Parse arguments
    for i, arg in enumerate(sys.argv[2:], start=2):
        if arg == '--no-volume':
            show_volume = False
        elif arg.isdigit():
            num_candles = int(arg)
    
    plot_interactive_chart(csv_file, num_candles, show_volume)


if __name__ == '__main__':
    main()
