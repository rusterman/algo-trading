# Drawdown Analysis - Dynamic DCA Level Integration

## Issue Fixed
The DRAWDOWN ANALYSIS section in the Excel report was using static hardcoded ranges (-5% to -10%, -10% to -20%, -20% to -30%, -30%+) that did not reflect the actual DCA levels configured in `strategy_config.json`.

## Solution
Modified `generate_excel_report.py` to dynamically generate drawdown ranges based on the actual DCA levels configured in the strategy.

---

## Changes Made

### Before
```
Static Ranges (hardcoded):
-5% to -10%      49 trades     9.00% max
-10% to -20%     18 trades     18.00% max
-20% to -30%     0 trades      0.00% max
-30%+            0 trades      0.00% max
```

### After
```
Dynamic Ranges (based on config):
0% to -6%        25 trades     6.00% max
-6% to -9%       96 trades     9.00% max
-9% to -12%      1 trade       12.00% max
-12% to -15%     0 trades      0.00% max
-15% to -18%     0 trades      0.00% max
-18%+            0 trades      0.00% max
```

(Example shows configuration with DCA levels: [-6, -9, -12, -15, -18])

---

## Technical Details

### Modified Method: `_calculate_drawdown_analysis()`

**Old Implementation:**
- Used hardcoded ranges: `-5% to -10%`, `-10% to -20%`, `-20% to -30%`, `-30%+`
- Ignored actual configuration

**New Implementation:**
1. Extracts DCA levels from `self.config.dca_levels`
2. Converts to positive values: [-6, -9, -12, -15, -18] → [6, 9, 12, 15, 18]
3. Creates dynamic range labels:
   - First range: `0% to -{first_level}%`
   - Intermediate: `-{level_i}% to -{level_i+1}%`
   - Last range: `-{deepest_level}%+`
4. Categorizes trades into appropriate ranges based on actual drawdown percentages

### Modified Display Logic

**Old Code:**
```python
for range_label in ['-5% to -10%', '-10% to -20%', '-20% to -30%', '-30%+']:
    # Static iteration
```

**New Code:**
```python
for range_label in sorted(drawdown_analysis.keys(), 
                          key=lambda x: float(x.split('%')[0].lstrip('-')) 
                              if x[0] == '-' else float(x.split('%')[0])):
    # Dynamic sorting preserves order
```

---

## Benefits

✓ **Reflects Real Configuration**: Ranges now match configured DCA levels
✓ **Flexible**: Automatically adjusts when DCA levels change
✓ **Accurate Categorization**: Trades are categorized correctly into appropriate drawdown ranges
✓ **No More Misleading Data**: Fixed ranges no longer show statistics for ranges outside configured levels

---

## Example Configurations

### Configuration 1: Conservative (Small Drawdowns)
```json
"dca_levels": [-2, -4, -8, -12, -16]
```
Generates ranges:
- 0% to -2%
- -2% to -4%
- -4% to -8%
- -8% to -12%
- -12% to -16%
- -16%+

### Configuration 2: Aggressive (Large Drawdowns)
```json
"dca_levels": [-10, -20, -30, -40]
```
Generates ranges:
- 0% to -10%
- -10% to -20%
- -20% to -30%
- -30% to -40%
- -40%+

### Configuration 3: Current (BTC Example)
```json
"dca_levels": [-6, -9, -12, -15, -18]
```
Generates ranges:
- 0% to -6%
- -6% to -9%
- -9% to -12%
- -12% to -15%
- -15% to -18%
- -18%+

---

## Testing

✓ Verified with current configuration [-6, -9, -12, -15, -18]
✓ Produces correct dynamic ranges
✓ Accurately categorizes 122 trades:
  - 25 trades in 0% to -6% range
  - 96 trades in -6% to -9% range
  - 1 trade in -9% to -12% range
  - 0 trades in remaining ranges

✓ Excel reports now show accurate, configuration-specific drawdown analysis

---

## File Modified

- `generate_excel_report.py`
  - `_calculate_drawdown_analysis()` method: Completely rewritten
  - Display logic in `generate()` method: Updated to use dynamic ranges

---

## Backward Compatibility

✓ Works with any DCA level configuration
✓ No changes to other report sections
✓ Existing functionality preserved
✓ Performance impact: minimal
