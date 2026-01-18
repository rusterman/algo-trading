"""
Validate wick calculations in preprocessed data
Checks if upper_wick and lower_wick are calculated correctly
"""
import pandas as pd
import sys
from pathlib import Path


def validate_wicks(preprocessed_file):
    """
    Validate wick calculations by recalculating and comparing
    
    Args:
        preprocessed_file: Path to preprocessed CSV file with wicks
    """
    print(f"Loading {preprocessed_file}...")
    df = pd.read_csv(preprocessed_file)
    
    # Standardize column names
    df.columns = df.columns.str.strip().str.lower()
    
    print(f"Loaded {len(df):,} rows")
    
    # Check if wick columns exist
    if 'upper_wick' not in df.columns or 'lower_wick' not in df.columns:
        print("ERROR: File does not contain upper_wick and lower_wick columns!")
        return
    
    print("\nRecalculating wicks from OHLC data...")
    
    # Recalculate wicks
    calculated_upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
    calculated_lower_wick = df[['open', 'close']].min(axis=1) - df['low']
    
    # Compare with existing values
    upper_wick_match = (df['upper_wick'] - calculated_upper_wick).abs() < 0.0001
    lower_wick_match = (df['lower_wick'] - calculated_lower_wick).abs() < 0.0001
    
    # Count mismatches
    upper_mismatches = (~upper_wick_match).sum()
    lower_mismatches = (~lower_wick_match).sum()
    
    print("\n" + "="*60)
    print("VALIDATION RESULTS")
    print("="*60)
    print(f"Total rows checked:        {len(df):,}")
    print(f"Upper wick mismatches:     {upper_mismatches}")
    print(f"Lower wick mismatches:     {lower_mismatches}")
    
    if upper_mismatches == 0 and lower_mismatches == 0:
        print("\n✓ ALL WICKS ARE VALID! Calculations are correct.")
    else:
        print("\n✗ ERRORS FOUND! Some wicks are miscalculated.")
        
        # Show examples of mismatches
        if upper_mismatches > 0:
            print("\nFirst 5 upper wick mismatches:")
            mismatch_rows = df[~upper_wick_match].head()
            for idx, row in mismatch_rows.iterrows():
                expected = calculated_upper_wick.iloc[idx]
                actual = row['upper_wick']
                print(f"  Row {idx}: Open={row['open']}, High={row['high']}, Close={row['close']}")
                print(f"    Expected: {expected:.8f}, Got: {actual:.8f}, Diff: {abs(expected-actual):.8f}")
        
        if lower_mismatches > 0:
            print("\nFirst 5 lower wick mismatches:")
            mismatch_rows = df[~lower_wick_match].head()
            for idx, row in mismatch_rows.iterrows():
                expected = calculated_lower_wick.iloc[idx]
                actual = row['lower_wick']
                print(f"  Row {idx}: Open={row['open']}, Low={row['low']}, Close={row['close']}")
                print(f"    Expected: {expected:.8f}, Got: {actual:.8f}, Diff: {abs(expected-actual):.8f}")
    
    # Show some statistics
    print("\n" + "="*60)
    print("WICK STATISTICS")
    print("="*60)
    print(f"Upper wick - Min: {df['upper_wick'].min():.2f}, Max: {df['upper_wick'].max():.2f}, Mean: {df['upper_wick'].mean():.2f}")
    print(f"Lower wick - Min: {df['lower_wick'].min():.2f}, Max: {df['lower_wick'].max():.2f}, Mean: {df['lower_wick'].mean():.2f}")
    
    # Check for negative wicks (which would be invalid)
    negative_upper = (df['upper_wick'] < 0).sum()
    negative_lower = (df['lower_wick'] < 0).sum()
    
    print("\n" + "="*60)
    print("SANITY CHECKS")
    print("="*60)
    print(f"Negative upper wicks:      {negative_upper} {'✗ INVALID!' if negative_upper > 0 else '✓'}")
    print(f"Negative lower wicks:      {negative_lower} {'✗ INVALID!' if negative_lower > 0 else '✓'}")
    
    # Check if high >= max(open, close)
    invalid_high = (df['high'] < df[['open', 'close']].max(axis=1)).sum()
    print(f"High < max(Open, Close):   {invalid_high} {'✗ INVALID!' if invalid_high > 0 else '✓'}")
    
    # Check if low <= min(open, close)
    invalid_low = (df['low'] > df[['open', 'close']].min(axis=1)).sum()
    print(f"Low > min(Open, Close):    {invalid_low} {'✗ INVALID!' if invalid_low > 0 else '✓'}")
    
    # Sample a few random rows to display
    print("\n" + "="*60)
    print("SAMPLE DATA (5 random rows)")
    print("="*60)
    sample = df.sample(min(5, len(df)))[['open', 'high', 'low', 'close', 'upper_wick', 'lower_wick']]
    for idx, row in sample.iterrows():
        print(f"\nRow {idx}:")
        print(f"  OHLC: O={row['open']:.2f}, H={row['high']:.2f}, L={row['low']:.2f}, C={row['close']:.2f}")
        print(f"  Wicks: Upper={row['upper_wick']:.2f}, Lower={row['lower_wick']:.2f}")
        print(f"  Verification: H-max(O,C)={row['high']-max(row['open'], row['close']):.2f}, min(O,C)-L={min(row['open'], row['close'])-row['low']:.2f}")
    
    print("\n" + "="*60)


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_wicks.py data/with_wicks/btc_15m_data_2018_to_2025_with_wicks.csv")
        print("\nOr validate all files:")
        print("python validate_wicks.py data/with_wicks/*.csv")
        
        # Auto-detect with_wicks files
        wicks_dir = Path('data/with_wicks')
        if wicks_dir.exists():
            csv_files = list(wicks_dir.glob('*_with_wicks.csv'))
            if csv_files:
                print(f"\nFound {len(csv_files)} preprocessed files. Validating all...\n")
                for csv_file in csv_files:
                    validate_wicks(csv_file)
                    print("\n")
        return
    
    # Validate specific file(s)
    for file_path in sys.argv[1:]:
        validate_wicks(file_path)
        if len(sys.argv) > 2:
            print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    main()
