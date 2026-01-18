"""
Add upper_wick and lower_wick columns to OHLCV data
Works with any coin and any timeframe
"""
import pandas as pd
import sys
from pathlib import Path


def add_wicks_to_data(input_file):
    """
    Add wick columns to OHLCV data
    
    Args:
        input_file: Path to input CSV file
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"Error: File not found: {input_file}")
        return
    
    # Load the data
    print(f"Loading {input_path.name}...")
    df = pd.read_csv(input_path)
    
    # Standardize column names to lowercase
    df.columns = df.columns.str.strip().str.lower()
    
    print(f"  Loaded {len(df):,} rows")
    
    # Calculate upper and lower wicks
    print("  Calculating wicks...")
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    
    # Create with_wicks folder if it doesn't exist
    wicks_dir = input_path.parent / 'with_wicks'
    wicks_dir.mkdir(exist_ok=True)
    
    # Generate output filename: original_name_with_wicks.csv
    output_name = input_path.stem + '_with_wicks' + input_path.suffix
    output_path = wicks_dir / output_name
    
    # Save the modified data
    print(f"  Saving to {output_path}...")
    df.to_csv(output_path, index=False)
    
    print(f"✓ Done! Added upper_wick and lower_wick columns\n")
    
    return output_path


def main():
    if len(sys.argv) > 1:
        # Process specific file(s) provided as arguments
        for file_path in sys.argv[1:]:
            add_wicks_to_data(file_path)
    else:
        # Process all CSV files in data/ folder
        data_dir = Path('data')
        csv_files = [f for f in data_dir.glob('*.csv')]
        
        if not csv_files:
            print("No CSV files found in data/ folder")
            print("\nUsage:")
            print("  python add_wicks.py                          # Process all CSV in data/")
            print("  python add_wicks.py data/btc_15m_data.csv    # Process specific file")
            return
        
        print(f"Found {len(csv_files)} CSV file(s) in data/\n")
        
        for csv_file in csv_files:
            add_wicks_to_data(csv_file)
        
        print(f"\nAll files saved to data/with_wicks/")


if __name__ == '__main__':
    main()
