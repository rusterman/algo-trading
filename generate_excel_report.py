#!/usr/bin/env python3
"""
Generate an investor-ready Excel report from DCA Strategy backtest output.
Parses terminal output and creates a structured, professional Excel workbook.
"""

import re
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, 
    numbers, DEFAULT_FONT
)
from openpyxl.utils import get_column_letter


class BacktestOutputParser:
    """Parse backtest terminal output to extract metrics."""
    
    def __init__(self, output: str):
        self.output = output
        self.metrics = {}
        self._parse()
    
    def _parse(self):
        """Extract all metrics from the output."""
        # Config section
        self.metrics['asset'] = self._extract_asset()
        self.metrics['csv_file'] = self._extract_csv_file()
        self.metrics['period_start'] = self._extract_start_date()
        self.metrics['period_end'] = self._extract_end_date()
        self.metrics['initial_budget'] = self._extract_initial_budget()
        self.metrics['dca_levels'] = self._extract_dca_levels()
        self.metrics['dca_allocations'] = self._extract_dca_allocations()
        self.metrics['take_profit'] = self._extract_take_profit()
        
        # Results section
        self.metrics['total_trades'] = self._extract_total_trades()
        self.metrics['winning_trades'] = self._extract_winning_trades()
        self.metrics['losing_trades'] = self._extract_losing_trades()
        self.metrics['win_rate'] = self._extract_win_rate()
        self.metrics['total_profit'] = self._extract_total_profit()
        self.metrics['roi'] = self._extract_roi()
        self.metrics['avg_trade_duration'] = self._extract_avg_trade_duration()
        self.metrics['min_duration'] = self._extract_min_duration()
        self.metrics['max_duration'] = self._extract_max_duration()
        self.metrics['average_win'] = self._extract_average_win()
        
        # Trades
        self.metrics['trades'] = self._extract_trades()
        
        # Calculate monthly stats
        self.metrics['monthly_stats'] = self._calculate_monthly_stats()
        
        # Calculate capital metrics
        self.metrics['capital_stats'] = self._calculate_capital_stats()
        
        # Drawdown analysis
        self.metrics['drawdown_analysis'] = self._calculate_drawdown_analysis()
        
        # Trade duration stats
        self.metrics['duration_stats'] = self._calculate_duration_stats()
    
    def _extract_asset(self) -> str:
        """Extract asset name from CSV file."""
        match = re.search(r'data/([a-zA-Z0-9]+)_', self.output)
        if match:
            return match.group(1).upper()
        return "UNKNOWN"
    
    def _extract_csv_file(self) -> str:
        """Extract CSV file name."""
        match = re.search(r'CSV File:\s+([^\n]+)', self.output)
        if match:
            return match.group(1).strip()
        return ""
    
    def _extract_start_date(self) -> str:
        """Extract start date."""
        match = re.search(r'Date Range:\s+(\d{4}-\d{2}-\d{2})', self.output)
        if match:
            return match.group(1)
        return ""
    
    def _extract_end_date(self) -> str:
        """Extract end date."""
        match = re.search(r'Date Range:.*?→\s*(\d{4}-\d{2}-\d{2})', self.output)
        if match:
            return match.group(1)
        return ""
    
    def _extract_initial_budget(self) -> float:
        """Extract initial budget."""
        match = re.search(r'Initial Budget:\s+\$([0-9,]+\.\d{2})', self.output)
        if match:
            return float(match.group(1).replace(',', ''))
        return 0.0
    
    def _extract_dca_levels(self) -> List[int]:
        """Extract DCA levels."""
        match = re.search(r'DCA Levels:\s+\[([-\d, ]+)\]', self.output)
        if match:
            levels_str = match.group(1)
            return [int(x.strip()) for x in levels_str.split(',')]
        return []
    
    def _extract_dca_allocations(self) -> List[float]:
        """Extract DCA allocations."""
        match = re.search(r'DCA Allocations:\s+\[([\$0-9\', ]+)\]', self.output)
        if match:
            alloc_str = match.group(1)
            allocations = []
            for val in re.findall(r'\$([0-9,]+)', alloc_str):
                allocations.append(float(val.replace(',', '')))
            return allocations
        return []
    
    def _extract_take_profit(self) -> float:
        """Extract take profit percentage."""
        match = re.search(r'Take Profit:\s+([+-]?\d+\.\d+)%', self.output)
        if match:
            return float(match.group(1))
        return 0.0
    
    def _extract_total_trades(self) -> int:
        """Extract total trades count."""
        match = re.search(r'Total Trades:\s+(\d+)', self.output)
        if match:
            return int(match.group(1))
        return 0
    
    def _extract_winning_trades(self) -> int:
        """Extract winning trades."""
        match = re.search(r'Winning Trades:\s+(\d+)', self.output)
        if match:
            return int(match.group(1))
        return 0
    
    def _extract_losing_trades(self) -> int:
        """Extract losing trades."""
        match = re.search(r'Losing Trades:\s+(\d+)', self.output)
        if match:
            return int(match.group(1))
        return 0
    
    def _extract_win_rate(self) -> float:
        """Extract win rate."""
        match = re.search(r'Winning Trades:\s+\d+\s+\(([0-9.]+)%\)', self.output)
        if match:
            return float(match.group(1))
        return 0.0
    
    def _extract_total_profit(self) -> float:
        """Extract total profit/loss."""
        match = re.search(r'Total Profit/Loss:\s+\$([0-9,.]+)', self.output)
        if match:
            return float(match.group(1).replace(',', ''))
        return 0.0
    
    def _extract_roi(self) -> float:
        """Extract ROI percentage."""
        match = re.search(r'ROI:\s+([0-9.]+)%', self.output)
        if match:
            return float(match.group(1))
        return 0.0
    
    def _extract_avg_trade_duration(self) -> float:
        """Extract average trade duration in days."""
        match = re.search(r'Avg Trade Duration:\s+([0-9.]+) days', self.output)
        if match:
            return float(match.group(1))
        return 0.0
    
    def _extract_min_duration(self) -> float:
        """Extract minimum duration."""
        match = re.search(r'Min/Max Duration:\s+([0-9.]+) /', self.output)
        if match:
            return float(match.group(1))
        return 0.0
    
    def _extract_max_duration(self) -> float:
        """Extract maximum duration."""
        match = re.search(r'Min/Max Duration:.*?/\s+([0-9.]+) day', self.output)
        if match:
            return float(match.group(1))
        return 0.0
    
    def _extract_average_win(self) -> float:
        """Extract average win."""
        match = re.search(r'Average Win:\s+\$([0-9,.]+)', self.output)
        if match:
            return float(match.group(1).replace(',', ''))
        return 0.0
    
    def _extract_trades(self) -> List[Dict[str, Any]]:
        """Extract individual trade details."""
        trades = []
        # Split by "Trade:" pattern
        trade_blocks = re.split(r'Trade:\s+', self.output)
        
        for block in trade_blocks[1:]:  # Skip first empty split
            trade = {}
            
            # Extract dates and duration
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+→\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', block)
            if date_match:
                trade['entry_date'] = date_match.group(1)
                trade['exit_date'] = date_match.group(2)
            
            duration_match = re.search(r'Duration:\s+([0-9.]+) days', block)
            if duration_match:
                trade['duration_days'] = float(duration_match.group(1))
            
            profit_match = re.search(r'Profit/Loss:\s+\$([0-9,.]+)', block)
            if profit_match:
                trade['profit'] = float(profit_match.group(1).replace(',', ''))
            
            invested_match = re.search(r'Total Invested:\s+\$([0-9,.]+)', block)
            if invested_match:
                trade['invested'] = float(invested_match.group(1).replace(',', ''))
            
            if trade and 'duration_days' in trade and 'profit' in trade:
                trades.append(trade)
        
        return trades
    
    def _calculate_monthly_stats(self) -> Dict[str, Dict[str, Any]]:
        """Calculate monthly performance statistics."""
        monthly = {}
        
        for trade in self.metrics.get('trades', []):
            if 'entry_date' not in trade:
                continue
            
            # Extract year-month from entry date
            month_str = trade['entry_date'][:7]  # YYYY-MM
            
            if month_str not in monthly:
                monthly[month_str] = {'trades': 0, 'profit': 0.0}
            
            monthly[month_str]['trades'] += 1
            monthly[month_str]['profit'] += trade.get('profit', 0.0)
        
        # Calculate profit percentage for each month
        initial_budget = self.metrics.get('initial_budget', 1.0)
        for month in monthly:
            monthly[month]['profit_pct'] = (monthly[month]['profit'] / initial_budget) * 100
        
        return monthly
    
    def _calculate_capital_stats(self) -> Dict[str, float]:
        """Calculate capital utilization statistics."""
        stats = {}
        
        trades = self.metrics.get('trades', [])
        if trades:
            invested_amounts = [t.get('invested', 0) for t in trades]
            initial_budget = self.metrics.get('initial_budget', 1.0)
            
            avg_capital_used = sum(invested_amounts) / len(invested_amounts)
            peak_capital_used = max(invested_amounts)
            
            stats['avg_capital_used_pct'] = (avg_capital_used / initial_budget) * 100
            stats['peak_capital_used_pct'] = (peak_capital_used / initial_budget) * 100
            stats['capital_buffer_pct'] = 100 - stats['peak_capital_used_pct']
            stats['capital_efficiency'] = self.metrics.get('total_profit', 0.0) / avg_capital_used if avg_capital_used > 0 else 0
        
        return stats
    
    def _calculate_drawdown_analysis(self) -> Dict[str, int]:
        """Analyze trades by drawdown ranges."""
        analysis = {
            '-5% to -10%': 0,
            '-10% to -20%': 0,
            '-20% to -30%': 0,
            '-30%+': 0
        }
        
        # For now, since we don't have detailed drawdown info per trade,
        # we'll return zeros (can be enhanced with more detailed parsing)
        return analysis
    
    def _calculate_duration_stats(self) -> Dict[str, Any]:
        """Calculate trade duration statistics."""
        stats = {}
        
        trades = self.metrics.get('trades', [])
        durations = [t.get('duration_days', 0) for t in trades if 'duration_days' in t]
        
        if durations:
            stats['avg_duration'] = sum(durations) / len(durations)
            stats['max_duration'] = max(durations)
            stats['min_duration'] = min(durations)
            stats['longer_than_30d'] = sum(1 for d in durations if d > 30)
        else:
            stats['avg_duration'] = 0
            stats['max_duration'] = 0
            stats['min_duration'] = 0
            stats['longer_than_30d'] = 0
        
        return stats


class ExcelReportGenerator:
    """Generate a professional Excel report from parsed metrics."""
    
    def __init__(self, metrics: Dict[str, Any]):
        self.metrics = metrics
        self.wb = openpyxl.Workbook()
        self.ws = self.wb.active
        self.ws.title = "Backtest Report"
        self.current_row = 1
        self._setup_styles()
    
    def _setup_styles(self):
        """Define reusable cell styles."""
        self.header_font = Font(bold=True, size=12, color="FFFFFF")
        self.header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        
        self.subheader_font = Font(bold=True, size=11, color="FFFFFF")
        self.subheader_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        
        self.label_font = Font(bold=True, size=10)
        self.label_fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
        
        self.border = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )
        
        self.center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
        self.right_align = Alignment(horizontal='right', vertical='center')
        self.left_align = Alignment(horizontal='left', vertical='center')
    
    def _set_column_widths(self):
        """Set appropriate column widths."""
        self.ws.column_dimensions['A'].width = 30
        self.ws.column_dimensions['B'].width = 20
        self.ws.column_dimensions['C'].width = 18
        self.ws.column_dimensions['D'].width = 18
        self.ws.column_dimensions['E'].width = 18
    
    def _add_section_header(self, title: str):
        """Add a section header with spacing."""
        if self.current_row > 1:
            self.current_row += 1
        
        self.ws.merge_cells(f'A{self.current_row}:E{self.current_row}')
        cell = self.ws[f'A{self.current_row}']
        cell.value = title
        cell.font = self.header_font
        cell.fill = self.header_fill
        cell.alignment = self.center_align
        self.current_row += 1
    
    def _add_key_value(self, label: str, value: Any, format_type: str = 'text'):
        """Add a labeled key-value pair."""
        cell_label = self.ws[f'A{self.current_row}']
        cell_label.value = label
        cell_label.font = self.label_font
        cell_label.fill = self.label_fill
        cell_label.border = self.border
        cell_label.alignment = self.left_align
        
        cell_value = self.ws[f'B{self.current_row}']
        cell_value.value = value
        cell_value.border = self.border
        cell_value.alignment = self.right_align
        
        if format_type == 'currency':
            cell_value.number_format = '$#,##0.00'
        elif format_type == 'percentage':
            cell_value.number_format = '0.00%'
        elif format_type == 'number':
            cell_value.number_format = '0.00'
        
        self.current_row += 1
    
    def _add_table_header(self, headers: List[str]):
        """Add a table header row."""
        for col_idx, header in enumerate(headers, 1):
            cell = self.ws.cell(row=self.current_row, column=col_idx)
            cell.value = header
            cell.font = self.subheader_font
            cell.fill = self.subheader_fill
            cell.border = self.border
            cell.alignment = self.center_align
        self.current_row += 1
    
    def _add_table_row(self, values: List[Any], formats: List[str] = None):
        """Add a table data row."""
        if formats is None:
            formats = ['text'] * len(values)
        
        for col_idx, (value, fmt) in enumerate(zip(values, formats), 1):
            cell = self.ws.cell(row=self.current_row, column=col_idx)
            cell.value = value
            cell.border = self.border
            cell.alignment = self.right_align if fmt != 'text' else self.center_align
            
            if fmt == 'currency':
                cell.number_format = '$#,##0.00'
            elif fmt == 'percentage':
                cell.number_format = '0.00%'
            elif fmt == 'number':
                cell.number_format = '0.00'
        
        self.current_row += 1
    
    def generate(self):
        """Generate the complete report."""
        self._set_column_widths()
        
        # Strategy Overview
        self._add_section_header("STRATEGY OVERVIEW")
        self._add_key_value("Asset", self.metrics['asset'])
        self._add_key_value("Period Start", self.metrics['period_start'])
        self._add_key_value("Period End", self.metrics['period_end'])
        self._add_key_value("Strategy Type", "Mean Reversion")
        self._add_key_value("Model", "DCA (Spot)")
        dca_levels_str = ", ".join([str(abs(x)) for x in self.metrics['dca_levels']])
        self._add_key_value("DCA Levels (%)", dca_levels_str)
        self._add_key_value("Take Profit (%)", self.metrics['take_profit'])
        
        # Core Performance Metrics
        self._add_section_header("CORE PERFORMANCE METRICS")
        self._add_key_value("Total Trades", self.metrics['total_trades'], 'number')
        self._add_key_value("Winning Trades", self.metrics['winning_trades'], 'number')
        self._add_key_value("Win Rate (%)", self.metrics['win_rate'] / 100, 'percentage')
        self._add_key_value("Losing Trades", self.metrics['losing_trades'], 'number')
        self._add_key_value("Loss Rate (%)", (100 - self.metrics['win_rate']) / 100, 'percentage')
        self._add_key_value("Total Net Profit ($)", self.metrics['total_profit'], 'currency')
        self._add_key_value("Total Net Profit (%)", self.metrics['roi'] / 100, 'percentage')
        
        # Calculate average monthly return
        monthly_returns = [m['profit_pct'] for m in self.metrics['monthly_stats'].values()]
        avg_monthly_return = sum(monthly_returns) / len(monthly_returns) if monthly_returns else 0
        self._add_key_value("Average Monthly Return (%)", avg_monthly_return / 100, 'percentage')
        
        # Monthly Performance Table
        self._add_section_header("MONTHLY PERFORMANCE")
        self._add_table_header(["Month", "Trade Count", "Profit ($)", "Profit (%)"])
        
        for month in sorted(self.metrics['monthly_stats'].keys()):
            stats = self.metrics['monthly_stats'][month]
            self._add_table_row(
                [month, stats['trades'], stats['profit'], stats['profit_pct'] / 100],
                ['text', 'number', 'currency', 'percentage']
            )
        
        # Capital Utilization & Efficiency
        self._add_section_header("CAPITAL UTILIZATION & EFFICIENCY")
        capital_stats = self.metrics['capital_stats']
        self._add_key_value("Average Capital Used (%)", capital_stats.get('avg_capital_used_pct', 0) / 100, 'percentage')
        self._add_key_value("Peak Capital Used (%)", capital_stats.get('peak_capital_used_pct', 0) / 100, 'percentage')
        self._add_key_value("Capital Buffer (Minimum Remaining %)", capital_stats.get('capital_buffer_pct', 0) / 100, 'percentage')
        self._add_key_value("Capital Efficiency", capital_stats.get('capital_efficiency', 0), 'number')
        
        # Drawdown Analysis
        self._add_section_header("DRAWDOWN ANALYSIS")
        self._add_table_header(["Drawdown Range", "Trade Count", "Max Drawdown (%)"])
        drawdown = self.metrics['drawdown_analysis']
        for range_label in ['-5% to -10%', '-10% to -20%', '-20% to -30%', '-30%+']:
            self._add_table_row(
                [range_label, drawdown.get(range_label, 0), 0],
                ['text', 'number', 'percentage']
            )
        
        # Trade Duration Statistics
        self._add_section_header("TRADE DURATION STATISTICS")
        duration_stats = self.metrics['duration_stats']
        self._add_key_value("Average Trade Duration (Days)", duration_stats.get('avg_duration', 0), 'number')
        self._add_key_value("Longest Trade Duration (Days)", duration_stats.get('max_duration', 0), 'number')
        self._add_key_value("Trades Longer Than 30 Days", duration_stats.get('longer_than_30d', 0), 'number')
        
        # Set print settings
        self.ws.page_setup.paperSize = self.ws.PAPERSIZE_LETTER
        self.ws.page_margins.left = 0.5
        self.ws.page_margins.right = 0.5
        self.ws.page_margins.top = 0.75
        self.ws.page_margins.bottom = 0.75
        
        return self.wb
    
    def save(self, filepath: str):
        """Save the workbook to a file."""
        self.wb.save(filepath)


def run_backtest() -> str:
    """Run the backtest and capture output."""
    result = subprocess.run(
        ['python', 'run_backtest.py'],
        capture_output=True,
        text=True,
        cwd='/Users/rustam/Desktop/projects/algo-trading'
    )
    return result.stdout + result.stderr


def main():
    """Main execution."""
    print("Running backtest...")
    output = run_backtest()
    
    print("Parsing backtest output...")
    parser = BacktestOutputParser(output)
    metrics = parser.metrics
    
    print(f"Asset: {metrics['asset']}")
    print(f"Total Trades: {metrics['total_trades']}")
    print(f"Total Profit: ${metrics['total_profit']:.2f}")
    
    print("Generating Excel report...")
    generator = ExcelReportGenerator(metrics)
    wb = generator.generate()
    
    # Generate filename with timestamp
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
    asset = metrics['asset']
    filename = f"{timestamp}-{asset}-backtest.xlsx"
    filepath = f"/Users/rustam/Desktop/projects/algo-trading/reports/{filename}"
    
    # Ensure reports directory exists
    Path('/Users/rustam/Desktop/projects/algo-trading/reports').mkdir(parents=True, exist_ok=True)
    
    generator.save(filepath)
    
    print(f"\n✓ Excel report generated successfully!")
    print(f"📊 File: {filepath}")
    
    return filepath


if __name__ == '__main__':
    main()
