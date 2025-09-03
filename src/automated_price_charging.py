#!/usr/bin/env python3
"""
GoodWe Dynamic Price Optimiser - Automated Price-Based Charging System
Integrates Polish electricity market prices with automatic charging control
"""

import asyncio
import json
import logging
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from pathlib import Path

# Import the GoodWe fast charging functionality
import sys
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from fast_charge import GoodWeFastCharger

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutomatedPriceCharger:
    """Automated charging system based on Polish electricity prices"""
    
    def __init__(self, config_path: str = None):
        """Initialize the automated charger"""
        if config_path is None:
            # Use absolute path to config directory
            current_dir = Path(__file__).parent.parent
            self.config_path = str(current_dir / "config" / "fast_charge_config.yaml")
        else:
            self.config_path = config_path
        self.goodwe_charger = GoodWeFastCharger(self.config_path)
        self.price_api_url = "https://api.raporty.pse.pl/api/csdac-pln"
        self.current_schedule = None
        self.is_charging = False
        self.charging_start_time = None
        
        # Load electricity pricing configuration
        self._load_pricing_config()
    
    def _load_pricing_config(self):
        """Load electricity pricing configuration from config file"""
        try:
            import yaml
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            pricing_config = config.get('electricity_pricing', {})
            self.sc_component_net = pricing_config.get('sc_component_net', 0.0892)
            self.sc_component_gross = pricing_config.get('sc_component_gross', 0.1097)
            self.minimum_price_floor = pricing_config.get('minimum_price_floor', 0.0050)
            self.charging_threshold_percentile = pricing_config.get('charging_threshold_percentile', 0.25)
            
            logger.info(f"Loaded pricing config: SC component = {self.sc_component_net} PLN/kWh")
            
        except Exception as e:
            logger.warning(f"Failed to load pricing config, using defaults: {e}")
            # Default values from Polish electricity pricing document
            self.sc_component_net = 0.0892
            self.sc_component_gross = 0.1097
            self.minimum_price_floor = 0.0050
            self.charging_threshold_percentile = 0.25
    
    def calculate_final_price(self, market_price: float) -> float:
        """Calculate final price including SC component (Składnik cenotwórczy)"""
        # According to Polish electricity pricing: Final Price = Market Price + SC Component
        final_price = market_price + self.sc_component_net
        return final_price
    
    def apply_minimum_price_floor(self, price: float) -> float:
        """Apply minimum price floor as per Polish regulations"""
        return max(price, self.minimum_price_floor)
        
    async def initialize(self) -> bool:
        """Initialize the system and connect to inverter"""
        logger.info("Initializing automated price-based charging system...")
        
        # Connect to GoodWe inverter
        if not await self.goodwe_charger.connect_inverter():
            logger.error("Failed to connect to GoodWe inverter")
            return False
        
        logger.info("Successfully connected to GoodWe inverter")
        return True
    
    def fetch_today_prices(self) -> Optional[Dict]:
        """Fetch today's electricity prices from Polish market using RCE-PLN API"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            # CSDAC-PLN API uses business_date field for filtering
            url = f"{self.price_api_url}?$filter=business_date%20eq%20'{today}'"
            
            logger.info(f"Fetching CSDAC price data for {today}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fetched {len(data.get('value', []))} CSDAC price points")
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch CSDAC price data: {e}")
            return None
    
    def analyze_charging_windows(self, price_data: Dict, 
                               target_hours: float = 4.0,
                               max_price_threshold: Optional[float] = None) -> List[Dict]:
        """Analyze price data and find optimal charging windows"""
        
        if not price_data or 'value' not in price_data:
            return []
        
        # Calculate price threshold if not provided
        if max_price_threshold is None:
            # Calculate final prices (market price + SC component) for threshold calculation
            final_prices = [self.calculate_final_price(float(item['csdac_pln'])) for item in price_data['value']]
            max_price_threshold = sorted(final_prices)[int(len(final_prices) * self.charging_threshold_percentile)]
        
        target_minutes = int(target_hours * 60)
        window_size = target_minutes // 15  # Number of 15-minute periods
        
        logger.info(f"Finding charging windows of {target_hours}h at max price {max_price_threshold:.2f} PLN/MWh (including SC component)")
        
        charging_windows = []
        
        # Slide through all possible windows
        for i in range(len(price_data['value']) - window_size + 1):
            window_data = price_data['value'][i:i + window_size]
            # Calculate final prices (market price + SC component) for each window
            window_final_prices = [self.calculate_final_price(float(item['csdac_pln'])) for item in window_data]
            avg_price = sum(window_final_prices) / len(window_final_prices)
            
            # Check if window meets criteria
            if avg_price <= max_price_threshold:
                start_time = datetime.strptime(window_data[0]['dtime'], '%Y-%m-%d %H:%M')
                end_time = datetime.strptime(window_data[-1]['dtime'], '%Y-%m-%d %H:%M') + timedelta(minutes=15)
                
                # Calculate savings using final prices (market price + SC component)
                all_final_prices = [self.calculate_final_price(float(item['csdac_pln'])) for item in price_data['value']]
                overall_avg = sum(all_final_prices) / len(all_final_prices)
                savings = overall_avg - avg_price
                
                window = {
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_minutes': target_minutes,
                    'avg_price': avg_price,
                    'savings': savings,
                    'savings_percent': (savings / overall_avg) * 100
                }
                charging_windows.append(window)
        
        # Sort by savings (highest first)
        charging_windows.sort(key=lambda x: x['savings'], reverse=True)
        
        logger.info(f"Found {len(charging_windows)} optimal charging windows")
        return charging_windows
    
    def get_current_price(self, price_data: Dict) -> Optional[float]:
        """Get current electricity price including SC component"""
        if not price_data or 'value' not in price_data:
            return None
        
        now = datetime.now()
        current_time = now.replace(second=0, microsecond=0)
        
        # Find the current 15-minute period
        for item in price_data['value']:
            item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
            if item_time <= current_time < item_time + timedelta(minutes=15):
                market_price = float(item['csdac_pln'])
                return self.calculate_final_price(market_price)
        
        return None
    
    def should_start_charging(self, price_data: Dict, 
                            max_price_threshold: Optional[float] = None) -> bool:
        """Determine if charging should start based on current price"""
        
        current_price = self.get_current_price(price_data)
        if current_price is None:
            logger.warning("Could not determine current price")
            return False
        
        # Calculate price threshold if not provided
        if max_price_threshold is None:
            # Calculate final prices (market price + SC component) for threshold calculation
            final_prices = [self.calculate_final_price(float(item['csdac_pln'])) for item in price_data['value']]
            max_price_threshold = sorted(final_prices)[int(len(final_prices) * self.charging_threshold_percentile)]
        
        should_charge = current_price <= max_price_threshold
        
        logger.info(f"Current price: {current_price:.2f} PLN/MWh, Threshold: {max_price_threshold:.2f} PLN/MWh, Should charge: {should_charge}")
        
        return should_charge
    
    async def start_price_based_charging(self, price_data: Dict) -> bool:
        """Start charging based on current electricity price"""
        
        if self.is_charging:
            logger.info("Already charging, skipping start request")
            return True
        
        if not self.should_start_charging(price_data):
            logger.info("Current price is not optimal for charging")
            return False
        
        logger.info("Starting price-based charging...")
        
        # Start fast charging
        if await self.goodwe_charger.start_fast_charging():
            self.is_charging = True
            self.charging_start_time = datetime.now()
            logger.info("Price-based charging started successfully")
            return True
        else:
            logger.error("Failed to start price-based charging")
            return False
    
    async def stop_price_based_charging(self) -> bool:
        """Stop price-based charging"""
        
        if not self.is_charging:
            logger.info("Not currently charging")
            return True
        
        logger.info("Stopping price-based charging...")
        
        if await self.goodwe_charger.stop_fast_charging():
            self.is_charging = False
            charging_duration = None
            if self.charging_start_time:
                charging_duration = datetime.now() - self.charging_start_time
            
            logger.info("Price-based charging stopped")
            if charging_duration:
                logger.info(f"Total charging time: {charging_duration}")
            
            return True
        else:
            logger.error("Failed to stop price-based charging")
            return False
    
    async def schedule_charging_for_today(self, max_charging_hours: float = 4.0):
        """Schedule charging for today's optimal window based on known prices"""
        
        logger.info("Scheduling charging for today's optimal window")
        
        # Fetch today's price data once
        price_data = self.fetch_today_prices()
        if not price_data:
            logger.error("Failed to fetch price data for scheduling")
            return False
        
        # Find optimal charging windows
        charging_windows = self.analyze_charging_windows(price_data, max_charging_hours)
        if not charging_windows:
            logger.warning("No optimal charging windows found for today")
            return False
        
        # Get the best window
        best_window = charging_windows[0]
        start_time_str = best_window['start_time']
        end_time_str = best_window['end_time']
        
        # Parse times
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S').time()
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S').time()
        
        logger.info(f"Optimal charging window: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        logger.info(f"Average price: {best_window['avg_price']:.2f} PLN/MWh")
        logger.info(f"Savings: {best_window['savings_per_mwh']:.2f} PLN/MWh")
        
        # Schedule the charging
        await self._execute_scheduled_charging(start_time, end_time, max_charging_hours)
        return True
    
    async def _execute_scheduled_charging(self, start_time: datetime.time, end_time: datetime.time, max_charging_hours: float):
        """Execute scheduled charging for the specified time window"""
        
        logger.info(f"Starting scheduled charging from {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}")
        
        try:
            while True:
                now = datetime.now()
                current_time = now.time()
                
                # Check if we're in the charging window
                if start_time <= current_time <= end_time:
                    if not self.is_charging:
                        logger.info(f"Starting charging at {current_time.strftime('%H:%M')} (scheduled window)")
                        await self.start_price_based_charging(None)  # No need for price data
                
                # Check if we should stop charging
                elif self.is_charging:
                    if current_time > end_time:
                        logger.info(f"Stopping charging at {current_time.strftime('%H:%M')} (end of scheduled window)")
                        await self.stop_price_based_charging()
                        break
                
                # Monitor charging status if active
                if self.is_charging:
                    # Check if we've been charging too long
                    if self.charging_start_time:
                        charging_duration = now - self.charging_start_time
                        if charging_duration.total_seconds() > max_charging_hours * 3600:
                            logger.info(f"Maximum charging time ({max_charging_hours}h) reached, stopping")
                            await self.stop_price_based_charging()
                            break
                    
                    # Check battery SoC
                    status = await self.goodwe_charger.get_charging_status()
                    if 'error' not in status:
                        battery_soc = status.get('current_battery_soc', 0)
                        target_soc = status.get('target_soc_percentage', 0)
                        logger.info(f"Charging in progress: Battery {battery_soc}% / Target {target_soc}%")
                        
                        # Check if target reached
                        if battery_soc >= target_soc:
                            logger.info("Target SoC reached, stopping charging")
                            await self.stop_price_based_charging()
                            break
                
                # Wait 1 minute before next check
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Scheduled charging interrupted by user")
            if self.is_charging:
                await self.stop_price_based_charging()
        except Exception as e:
            logger.error(f"Scheduled charging error: {e}")
            if self.is_charging:
                await self.stop_price_based_charging()
    
    async def schedule_charging_for_tomorrow(self, max_charging_hours: float = 4.0):
        """Schedule charging for tomorrow's optimal window"""
        
        logger.info("Scheduling charging for tomorrow's optimal window")
        
        # Get tomorrow's date
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        # Fetch tomorrow's price data
        price_data = self.fetch_price_data_for_date(tomorrow_str)
        if not price_data:
            logger.error(f"Failed to fetch price data for {tomorrow_str}")
            return False
        
        # Find optimal charging windows for tomorrow
        charging_windows = self.analyze_charging_windows(price_data, max_charging_hours)
        if not charging_windows:
            logger.warning(f"No optimal charging windows found for {tomorrow_str}")
            return False
        
        # Get the best window
        best_window = charging_windows[0]
        start_time_str = best_window['start_time']
        end_time_str = best_window['end_time']
        
        # Parse times
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S').time()
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S').time()
        
        logger.info(f"Tomorrow's optimal charging window: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        logger.info(f"Average price: {best_window['avg_price']:.2f} PLN/MWh")
        logger.info(f"Savings: {best_window['savings_per_mwh']:.2f} PLN/MWh")
        
        # Schedule the charging for tomorrow
        await self._execute_scheduled_charging(start_time, end_time, max_charging_hours)
        return True
    
    def fetch_price_data_for_date(self, date_str: str) -> Dict:
        """Fetch price data for a specific date"""
        try:
            url = f"{self.price_api_url}?$filter=business_date%20eq%20'{date_str}'"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch price data for {date_str}: {e}")
            return None
    
    def print_daily_schedule(self, price_data: Dict):
        """Print today's charging schedule"""
        if not price_data or 'value' not in price_data:
            print("No price data available")
            return
        
        print("\n" + "="*80)
        print("TODAY'S ELECTRICITY PRICE SCHEDULE (with SC Component)")
        print("="*80)
        print(f"SC Component: {self.sc_component_net} PLN/kWh (Składnik cenotwórczy)")
        print("="*80)
        
        # Group prices by hour for better readability
        hourly_prices = {}
        for item in price_data['value']:
            time_str = item['dtime']
            hour = time_str.split(' ')[1][:5]  # Extract HH:MM
            market_price = float(item['csdac_pln'])
            final_price = self.calculate_final_price(market_price)
            
            if hour not in hourly_prices:
                hourly_prices[hour] = {'market': [], 'final': []}
            hourly_prices[hour]['market'].append(market_price)
            hourly_prices[hour]['final'].append(final_price)
        
        # Print hourly summary
        for hour in sorted(hourly_prices.keys()):
            market_prices = hourly_prices[hour]['market']
            final_prices = hourly_prices[hour]['final']
            avg_market_price = sum(market_prices) / len(market_prices)
            avg_final_price = sum(final_prices) / len(final_prices)
            min_final_price = min(final_prices)
            max_final_price = max(final_prices)
            
            # Color coding based on final price (with SC component)
            if avg_final_price <= 300:
                price_indicator = "🟢 LOW"
            elif avg_final_price <= 500:
                price_indicator = "🟡 MEDIUM"
            else:
                price_indicator = "🔴 HIGH"
            
            print(f"{hour:5} | Market: {avg_market_price:6.1f} | Final: {avg_final_price:6.1f} PLN/MWh | Range: {min_final_price:6.1f}-{max_final_price:6.1f} | {price_indicator}")
        
        # Find optimal charging windows
        charging_windows = self.analyze_charging_windows(price_data, target_hours=4.0)
        
        if charging_windows:
            print(f"\n🎯 OPTIMAL CHARGING WINDOWS (4h duration):")
            for i, window in enumerate(charging_windows[:3], 1):  # Show top 3
                print(f"  {i}. {window['start_time'].strftime('%H:%M')} - {window['end_time'].strftime('%H:%M')} "
                      f"| Avg: {window['avg_price']:.1f} PLN/MWh | Savings: {window['savings_percent']:.1f}%")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Automated Price-Based Charging System for GoodWe Inverter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in interactive mode (default)
  python automated_price_charging.py
  
  # Schedule charging for today's optimal window
  python automated_price_charging.py --schedule-today
  
  # Schedule charging for tomorrow's optimal window
  python automated_price_charging.py --schedule-tomorrow
  
  # Show current status and exit
  python automated_price_charging.py --status
  
  # Start charging now if price is optimal
  python automated_price_charging.py --start-now
  
  # Stop charging if active
  python automated_price_charging.py --stop
  
  # Use custom config file
  python automated_price_charging.py --config my_config.yaml --schedule-today
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/fast_charge_config.yaml',
        help='Configuration file path (default: config/fast_charge_config.yaml)'
    )
    
    parser.add_argument(
        '--schedule-today', '-m',
        action='store_true',
        help='Schedule charging for today\'s optimal window'
    )
    
    parser.add_argument(
        '--schedule-tomorrow', '-M',
        action='store_true',
        help='Schedule charging for tomorrow\'s optimal window'
    )
    
    parser.add_argument(
        '--start-now', '-s',
        action='store_true',
        help='Start charging now if price is optimal'
    )
    
    parser.add_argument(
        '--stop', '-x',
        action='store_true',
        help='Stop charging if active'
    )
    
    parser.add_argument(
        '--status', '-t',
        action='store_true',
        help='Show current status and exit'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Run in interactive mode with menu (default is non-interactive)'
    )
    
    return parser.parse_args()

async def main():
    """Main function"""
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Configuration
    config_file = args.config
    
    if not Path(config_file).exists():
        print(f"Configuration file {config_file} not found!")
        print("Please ensure the GoodWe inverter configuration is set up first.")
        return
    
    # Initialize automated charger
    charger = AutomatedPriceCharger(config_file)
    
    if not await charger.initialize():
        print("Failed to initialize automated charger")
        return
    
    # Get today's price data and show schedule
    print("Fetching today's electricity prices...")
    price_data = charger.fetch_today_prices()
    
    if not price_data:
        print("Failed to fetch price data. Check your internet connection.")
        return
    
    charger.print_daily_schedule(price_data)
    
    # Handle command-line arguments
    if args.schedule_today:
        print("\n🚀 Scheduling charging for today's optimal window...")
        print("Press Ctrl+C to stop scheduled charging")
        await charger.schedule_charging_for_today(max_charging_hours=4.0)
        return
        
    elif args.schedule_tomorrow:
        print("\n🚀 Scheduling charging for tomorrow's optimal window...")
        print("Press Ctrl+C to stop scheduled charging")
        await charger.schedule_charging_for_tomorrow(max_charging_hours=4.0)
        return
        
    elif args.start_now:
        print("\n🔌 Starting charging now if price is optimal...")
        if await charger.start_price_based_charging(price_data):
            print("✅ Charging started based on current prices!")
        else:
            print("❌ Could not start charging (check logs for details)")
        return
        
    elif args.stop:
        print("\n⏹️ Stopping charging if active...")
        if await charger.stop_price_based_charging():
            print("✅ Charging stopped!")
        else:
            print("❌ Could not stop charging (check logs for details)")
        return
        
    elif args.status:
        print("\n📊 Current Status:")
        status = await charger.goodwe_charger.get_charging_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        return
    
    # If no specific action requested, show analysis and exit (non-interactive by default)
    if args.interactive:
        print("\n" + "="*60)
        print("AUTOMATED CHARGING OPTIONS:")
        print("1. Schedule charging for today's optimal window")
        print("2. Schedule charging for tomorrow's optimal window")
        print("3. Show current status")
        print("4. Start charging now (if price is optimal)")
        print("5. Stop charging (if active)")
        print("6. Exit")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-6): ").strip()
                
                if choice == "1":
                    print("Scheduling charging for today's optimal window...")
                    print("Press Ctrl+C to stop scheduled charging")
                    await charger.schedule_charging_for_today(max_charging_hours=4.0)
                    break
                    
                elif choice == "2":
                    print("Scheduling charging for tomorrow's optimal window...")
                    print("Press Ctrl+C to stop scheduled charging")
                    await charger.schedule_charging_for_tomorrow(max_charging_hours=4.0)
                    break
                    
                elif choice == "3":
                    status = await charger.goodwe_charger.get_charging_status()
                    print("\nCurrent Status:")
                    for key, value in status.items():
                        print(f"  {key}: {value}")
                        
                elif choice == "4":
                    if await charger.start_price_based_charging(price_data):
                        print("✅ Charging started based on current prices!")
                    else:
                        print("❌ Could not start charging (check logs for details)")
                        
                elif choice == "5":
                    if await charger.stop_price_based_charging():
                        print("✅ Charging stopped!")
                    else:
                        print("❌ Could not stop charging (check logs for details)")
                        
                elif choice == "6":
                    print("Exiting...")
                    break
                    
                else:
                    print("Invalid choice. Please enter 1-6.")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
    else:
        print("\n" + "="*60)
        print("AUTOMATED CHARGING ANALYSIS COMPLETE")
        print("="*60)
        print("Use --help to see available command-line options for automation.")
        print("Example: python automated_price_charging.py --schedule-today")
        print("Example: python automated_price_charging.py --schedule-tomorrow")
        print("Example: python automated_price_charging.py --start-now")
        print("Example: python automated_price_charging.py --status")
        print("Example: python automated_price_charging.py --interactive")

if __name__ == "__main__":
    asyncio.run(main())
