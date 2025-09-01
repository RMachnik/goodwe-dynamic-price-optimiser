#!/usr/bin/env python3
"""
Polish Electricity Market Analyzer for GoodWe Inverter
Analyzes electricity prices and creates optimal charging schedules
"""

import asyncio
import json
import logging
import requests
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import statistics
from dataclasses import dataclass

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PricePoint:
    """Represents a single price point"""
    time: datetime
    price_pln: float
    period: str
    is_charging_window: bool = False

@dataclass
class ChargingWindow:
    """Represents an optimal charging window"""
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    avg_price: float
    total_cost_per_mwh: float
    savings_per_mwh: float

class PolishElectricityAnalyzer:
    """Analyzes Polish electricity prices and creates charging schedules"""
    
    def __init__(self):
        self.base_url = "https://api.raporty.pse.pl/api/csdac-pln"
        self.price_data: List[PricePoint] = []
        self.charging_windows: List[ChargingWindow] = []
        
    def fetch_price_data(self, date: str) -> List[PricePoint]:
        """Fetch electricity price data for a specific date"""
        try:
            # Format date for API (YYYY-MM-DD)
            if isinstance(date, datetime):
                date_str = date.strftime('%Y-%m-%d')
            else:
                date_str = date
                
            url = f"{self.base_url}?$filter=business_date%20eq%20'{date_str}'"
            logger.info(f"Fetching price data for {date_str}")
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            price_points = []
            
            for item in data.get('value', []):
                # Parse time (format: "2025-08-31 00:15")
                time_str = item['dtime']
                price = float(item['csdac_pln'])
                period = item['period']
                
                # Convert to datetime
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
                
                price_points.append(PricePoint(
                    time=dt,
                    price_pln=price,
                    period=period
                ))
            
            self.price_data = sorted(price_points, key=lambda x: x.time)
            logger.info(f"Fetched {len(self.price_data)} price points for {date_str}")
            return self.price_data
            
        except Exception as e:
            logger.error(f"Failed to fetch price data: {e}")
            return []
    
    def analyze_prices(self) -> Dict[str, float]:
        """Analyze price statistics"""
        if not self.price_data:
            return {}
        
        prices = [p.price_pln for p in self.price_data]
        
        analysis = {
            'min_price': min(prices),
            'max_price': max(prices),
            'avg_price': statistics.mean(prices),
            'median_price': statistics.median(prices),
            'std_dev': statistics.stdev(prices) if len(prices) > 1 else 0,
            'total_periods': len(prices)
        }
        
        # Find price percentiles
        sorted_prices = sorted(prices)
        analysis['price_25th_percentile'] = sorted_prices[int(len(sorted_prices) * 0.25)]
        analysis['price_75th_percentile'] = sorted_prices[int(len(sorted_prices) * 0.75)]
        
        return analysis
    
    def find_optimal_charging_windows(self, 
                                    target_duration_hours: float = 4.0,
                                    max_price_threshold: Optional[float] = None,
                                    min_savings_percent: float = 20.0) -> List[ChargingWindow]:
        """Find optimal charging windows based on price analysis"""
        
        if not self.price_data:
            logger.warning("No price data available")
            return []
        
        # Calculate price threshold if not provided
        if max_price_threshold is None:
            analysis = self.analyze_prices()
            max_price_threshold = analysis['price_25th_percentile']  # Use 25th percentile as threshold
        
        target_minutes = int(target_duration_hours * 60)
        window_size = target_minutes // 15  # Number of 15-minute periods
        
        logger.info(f"Finding charging windows of {target_duration_hours}h at max price {max_price_threshold:.2f} PLN/MWh")
        
        charging_windows = []
        
        # Slide through all possible windows
        for i in range(len(self.price_data) - window_size + 1):
            window_prices = self.price_data[i:i + window_size]
            avg_price = statistics.mean([p.price_pln for p in window_prices])
            
            # Check if window meets criteria
            if avg_price <= max_price_threshold:
                start_time = window_prices[0].time
                end_time = window_prices[-1].time + timedelta(minutes=15)
                
                # Calculate savings compared to average price
                overall_avg = statistics.mean([p.price_pln for p in self.price_data])
                savings_per_mwh = overall_avg - avg_price
                savings_percent = (savings_per_mwh / overall_avg) * 100
                
                if savings_percent >= min_savings_percent:
                    window = ChargingWindow(
                        start_time=start_time,
                        end_time=end_time,
                        duration_minutes=target_minutes,
                        avg_price=avg_price,
                        total_cost_per_mwh=avg_price * (target_minutes / 60),
                        savings_per_mwh=savings_per_mwh
                    )
                    charging_windows.append(window)
        
        # Sort by savings (highest first)
        charging_windows.sort(key=lambda x: x.savings_per_mwh, reverse=True)
        
        self.charging_windows = charging_windows
        logger.info(f"Found {len(charging_windows)} optimal charging windows")
        
        return charging_windows
    
    def get_daily_charging_schedule(self, 
                                  target_charge_hours: float = 4.0,
                                  max_windows: int = 3) -> List[ChargingWindow]:
        """Get daily charging schedule with multiple windows"""
        
        # Find all optimal windows
        all_windows = self.find_optimal_charging_windows(
            target_duration_hours=target_charge_hours,
            min_savings_percent=15.0
        )
        
        # Select top windows, ensuring no overlap
        selected_windows = []
        used_times = set()
        
        for window in all_windows:
            if len(selected_windows) >= max_windows:
                break
                
            # Check for overlap
            overlap = False
            window_start = window.start_time
            window_end = window.end_time
            
            for used_start, used_end in used_times:
                if (window_start < used_end and window_end > used_start):
                    overlap = True
                    break
            
            if not overlap:
                selected_windows.append(window)
                used_times.add((window_start, window_end))
        
        return selected_windows
    
    def print_price_analysis(self):
        """Print comprehensive price analysis"""
        if not self.price_data:
            print("No price data available")
            return
        
        analysis = self.analyze_prices()
        
        print("\n" + "="*60)
        print("POLISH ELECTRICITY MARKET ANALYSIS")
        print("="*60)
        print(f"Date: {self.price_data[0].time.strftime('%Y-%m-%d')}")
        print(f"Total periods: {analysis['total_periods']} (15-minute intervals)")
        print(f"Time range: {self.price_data[0].time.strftime('%H:%M')} - {self.price_data[-1].time.strftime('%H:%M')}")
        print()
        
        print("PRICE STATISTICS (PLN/MWh):")
        print(f"  Minimum:     {analysis['min_price']:8.2f}")
        print(f"  Maximum:     {analysis['max_price']:8.2f}")
        print(f"  Average:     {analysis['avg_price']:8.2f}")
        print(f"  Median:      {analysis['median_price']:8.2f}")
        print(f"  25th %ile:   {analysis['price_25th_percentile']:8.2f}")
        print(f"  75th %ile:   {analysis['price_75th_percentile']:8.2f}")
        print(f"  Std Dev:     {analysis['std_dev']:8.2f}")
        
        # Price distribution
        print("\nPRICE DISTRIBUTION:")
        price_ranges = [
            (0, 200, "Very Low (0-200 PLN/MWh)"),
            (200, 400, "Low (200-400 PLN/MWh)"),
            (400, 600, "Medium (400-600 PLN/MWh)"),
            (600, 800, "High (600-800 PLN/MWh)"),
            (800, 1000, "Very High (800+ PLN/MWh)")
        ]
        
        for min_price, max_price, label in price_ranges:
            count = sum(1 for p in self.price_data if min_price <= p.price_pln < max_price)
            percentage = (count / len(self.price_data)) * 100
            print(f"  {label:25} {count:3d} periods ({percentage:5.1f}%)")
    
    def print_charging_windows(self, windows: List[ChargingWindow]):
        """Print optimal charging windows"""
        if not windows:
            print("No optimal charging windows found")
            return
        
        print("\n" + "="*60)
        print("OPTIMAL CHARGING WINDOWS")
        print("="*60)
        
        for i, window in enumerate(windows, 1):
            print(f"\nWindow {i}:")
            print(f"  Time:        {window.start_time.strftime('%H:%M')} - {window.end_time.strftime('%H:%M')}")
            print(f"  Duration:    {window.duration_minutes} minutes ({window.duration_minutes/60:.1f} hours)")
            print(f"  Avg Price:   {window.avg_price:.2f} PLN/MWh")
            print(f"  Total Cost:  {window.total_cost_per_mwh:.2f} PLN/MWh")
            print(f"  Savings:     {window.savings_per_mwh:.2f} PLN/MWh")
            
            # Calculate percentage savings
            overall_avg = statistics.mean([p.price_pln for p in self.price_data])
            savings_percent = (window.savings_per_mwh / overall_avg) * 100
            print(f"  Savings %:   {savings_percent:.1f}%")
    
    def export_schedule_to_json(self, filename: str, windows: List[ChargingWindow]):
        """Export charging schedule to JSON file"""
        schedule_data = {
            'date': self.price_data[0].time.strftime('%Y-%m-%d') if self.price_data else None,
            'analysis': self.analyze_prices(),
            'charging_windows': [
                {
                    'start_time': w.start_time.isoformat(),
                    'end_time': w.end_time.isoformat(),
                    'duration_minutes': w.duration_minutes,
                    'avg_price': w.avg_price,
                    'total_cost_per_mwh': w.total_cost_per_mwh,
                    'savings_per_mwh': w.savings_per_mwh
                }
                for w in windows
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Schedule exported to {filename}")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Polish Electricity Market Analyzer for GoodWe Inverter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze today's prices (default)
  python polish_electricity_analyzer.py
  
  # Analyze specific date
  python polish_electricity_analyzer.py --date 2025-08-31
  
  # Custom charging duration and windows
  python polish_electricity_analyzer.py --duration 6.0 --windows 5
  
  # Export to custom filename
  python polish_electricity_analyzer.py --output my_schedule.json
  
  # Show help
  python polish_electricity_analyzer.py --help
        """
    )
    
    parser.add_argument(
        '--date', '-d',
        default=datetime.now().strftime('%Y-%m-%d'),
        help='Date to analyze (YYYY-MM-DD format, default: today)'
    )
    
    parser.add_argument(
        '--duration', '-t',
        type=float,
        default=4.0,
        metavar='HOURS',
        help='Target charging duration in hours (default: 4.0)'
    )
    
    parser.add_argument(
        '--windows', '-w',
        type=int,
        default=3,
        metavar='COUNT',
        help='Maximum number of charging windows to find (default: 3)'
    )
    
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='Output JSON filename (default: charging_schedule_YYYY-MM-DD.json)'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Quiet mode - minimal output'
    )
    
    return parser.parse_args()

async def main():
    """Main function to demonstrate the analyzer"""
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Import Path for file operations
    from pathlib import Path
    
    analyzer = PolishElectricityAnalyzer()
    
    # Fetch data for specified date
    print("Fetching Polish electricity market data...")
    price_data = analyzer.fetch_price_data(args.date)
    
    if not price_data:
        print("Failed to fetch price data")
        return
    
    # Analyze prices
    if not args.quiet:
        analyzer.print_price_analysis()
    
    # Find optimal charging windows
    print("\nAnalyzing optimal charging windows...")
    charging_windows = analyzer.get_daily_charging_schedule(
        target_charge_hours=args.duration,
        max_windows=args.windows
    )
    
    # Display results
    if not args.quiet:
        analyzer.print_charging_windows(charging_windows)
    
    # Export schedule to out directory
    if args.output:
        output_file = args.output
    else:
        # Create out directory if it doesn't exist
        out_dir = Path(__file__).parent.parent / "out"
        out_dir.mkdir(exist_ok=True)
        output_file = out_dir / f"charging_schedule_{args.date}.json"
    
    analyzer.export_schedule_to_json(str(output_file), charging_windows)
    
    if not args.quiet:
        print(f"\nAnalysis complete! Found {len(charging_windows)} optimal charging windows.")
    print(f"Schedule exported to '{output_file}'")

if __name__ == "__main__":
    asyncio.run(main())
