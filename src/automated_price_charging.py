#!/usr/bin/env python3
"""
Automated Price-Based Charging System for GoodWe Inverter
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
        """Fetch today's electricity prices from Polish market"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            url = f"{self.price_api_url}?$filter=business_date%20eq%20'{today}'"
            
            logger.info(f"Fetching price data for {today}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fetched {len(data.get('value', []))} price points")
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch price data: {e}")
            return None
    
    def analyze_charging_windows(self, price_data: Dict, 
                               target_hours: float = 4.0,
                               max_price_threshold: Optional[float] = None) -> List[Dict]:
        """Analyze price data and find optimal charging windows"""
        
        if not price_data or 'value' not in price_data:
            return []
        
        # Calculate price threshold if not provided
        if max_price_threshold is None:
            prices = [float(item['csdac_pln']) for item in price_data['value']]
            max_price_threshold = sorted(prices)[int(len(prices) * 0.25)]  # 25th percentile
        
        target_minutes = int(target_hours * 60)
        window_size = target_minutes // 15  # Number of 15-minute periods
        
        logger.info(f"Finding charging windows of {target_hours}h at max price {max_price_threshold:.2f} PLN/MWh")
        
        charging_windows = []
        
        # Slide through all possible windows
        for i in range(len(price_data['value']) - window_size + 1):
            window_data = price_data['value'][i:i + window_size]
            window_prices = [float(item['csdac_pln']) for item in window_data]
            avg_price = sum(window_prices) / len(window_prices)
            
            # Check if window meets criteria
            if avg_price <= max_price_threshold:
                start_time = datetime.strptime(window_data[0]['dtime'], '%Y-%m-%d %H:%M')
                end_time = datetime.strptime(window_data[-1]['dtime'], '%Y-%m-%d %H:%M') + timedelta(minutes=15)
                
                # Calculate savings
                all_prices = [float(item['csdac_pln']) for item in price_data['value']]
                overall_avg = sum(all_prices) / len(all_prices)
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
        """Get current electricity price"""
        if not price_data or 'value' not in price_data:
            return None
        
        now = datetime.now()
        current_time = now.replace(second=0, microsecond=0)
        
        # Find the current 15-minute period
        for item in price_data['value']:
            item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
            if item_time <= current_time < item_time + timedelta(minutes=15):
                return float(item['csdac_pln'])
        
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
            prices = [float(item['csdac_pln']) for item in price_data['value']]
            max_price_threshold = sorted(prices)[int(len(prices) * 0.25)]  # 25th percentile
        
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
    
    async def monitor_and_control(self, 
                                check_interval_minutes: int = 15,
                                max_charging_hours: float = 4.0,
                                auto_stop: bool = True):
        """Main monitoring and control loop"""
        
        logger.info(f"Starting price-based charging monitor (check every {check_interval_minutes} minutes)")
        
        try:
            while True:
                now = datetime.now()
                logger.info(f"Checking prices at {now.strftime('%H:%M:%S')}")
                
                # Fetch current price data
                price_data = self.fetch_today_prices()
                if not price_data:
                    logger.warning("Failed to fetch price data, waiting for next check")
                    await asyncio.sleep(check_interval_minutes * 60)
                    continue
                
                # Check if we should start charging
                if not self.is_charging:
                    if self.should_start_charging(price_data):
                        await self.start_price_based_charging(price_data)
                    else:
                        logger.info("Current price not optimal for charging")
                
                # Check if we should stop charging
                elif self.is_charging:
                    # Check if we've been charging too long
                    if auto_stop and self.charging_start_time:
                        charging_duration = now - self.charging_start_time
                        if charging_duration.total_seconds() > max_charging_hours * 3600:
                            logger.info(f"Maximum charging time ({max_charging_hours}h) reached, stopping")
                            await self.stop_price_based_charging()
                            continue
                    
                    # Check if price is no longer optimal
                    if not self.should_start_charging(price_data):
                        logger.info("Price no longer optimal, stopping charging")
                        await self.stop_price_based_charging()
                        continue
                    
                    # Get current status
                    status = await self.goodwe_charger.get_charging_status()
                    if 'error' not in status:
                        battery_soc = status.get('current_battery_soc', 0)
                        target_soc = status.get('target_soc_percentage', 0)
                        logger.info(f"Charging in progress: Battery {battery_soc}% / Target {target_soc}%")
                        
                        # Check if target reached
                        if battery_soc >= target_soc:
                            logger.info("Target SoC reached, stopping charging")
                            await self.stop_price_based_charging()
                            continue
                
                # Wait for next check
                logger.info(f"Waiting {check_interval_minutes} minutes until next price check...")
                await asyncio.sleep(check_interval_minutes * 60)
                
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
            if self.is_charging:
                await self.stop_price_based_charging()
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            if self.is_charging:
                await self.stop_price_based_charging()
    
    def print_daily_schedule(self, price_data: Dict):
        """Print today's charging schedule"""
        if not price_data or 'value' not in price_data:
            print("No price data available")
            return
        
        print("\n" + "="*60)
        print("TODAY'S ELECTRICITY PRICE SCHEDULE")
        print("="*60)
        
        # Group prices by hour for better readability
        hourly_prices = {}
        for item in price_data['value']:
            time_str = item['dtime']
            hour = time_str.split(' ')[1][:5]  # Extract HH:MM
            price = float(item['csdac_pln'])
            
            if hour not in hourly_prices:
                hourly_prices[hour] = []
            hourly_prices[hour].append(price)
        
        # Print hourly summary
        for hour in sorted(hourly_prices.keys()):
            prices = hourly_prices[hour]
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            
            # Color coding based on price
            if avg_price <= 300:
                price_indicator = "🟢 LOW"
            elif avg_price <= 500:
                price_indicator = "🟡 MEDIUM"
            else:
                price_indicator = "🔴 HIGH"
            
            print(f"{hour:5} | {avg_price:6.1f} PLN/MWh | {min_price:6.1f}-{max_price:6.1f} | {price_indicator}")
        
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
  
  # Start automated monitoring and charging
  python automated_price_charging.py --monitor
  
  # Show current status and exit
  python automated_price_charging.py --status
  
  # Start charging now if price is optimal
  python automated_price_charging.py --start-now
  
  # Stop charging if active
  python automated_price_charging.py --stop
  
  # Use custom config file
  python automated_price_charging.py --config my_config.yaml --monitor
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/fast_charge_config.yaml',
        help='Configuration file path (default: config/fast_charge_config.yaml)'
    )
    
    parser.add_argument(
        '--monitor', '-m',
        action='store_true',
        help='Start automated monitoring and charging'
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
        '--non-interactive', '-n',
        action='store_true',
        help='Run in non-interactive mode (useful for automation)'
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
    if args.monitor:
        print("\n🚀 Starting automated price-based charging monitor...")
        print("Press Ctrl+C to stop monitoring")
        await charger.monitor_and_control(check_interval_minutes=15)
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
    
    # If no specific action requested, show interactive menu
    if not args.non_interactive:
        print("\n" + "="*60)
        print("AUTOMATED CHARGING OPTIONS:")
        print("1. Start monitoring and automatic charging")
        print("2. Show current status")
        print("3. Start charging now (if price is optimal)")
        print("4. Stop charging (if active)")
        print("5. Exit")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-5): ").strip()
                
                if choice == "1":
                    print("Starting automated price-based charging monitor...")
                    print("Press Ctrl+C to stop monitoring")
                    await charger.monitor_and_control(check_interval_minutes=15)
                    break
                    
                elif choice == "2":
                    status = await charger.goodwe_charger.get_charging_status()
                    print("\nCurrent Status:")
                    for key, value in status.items():
                        print(f"  {key}: {value}")
                        
                elif choice == "3":
                    if await charger.start_price_based_charging(price_data):
                        print("✅ Charging started based on current prices!")
                    else:
                        print("❌ Could not start charging (check logs for details)")
                        
                elif choice == "4":
                    if await charger.stop_price_based_charging():
                        print("✅ Charging stopped!")
                    else:
                        print("❌ Could not stop charging (check logs for details)")
                        
                elif choice == "5":
                    print("Exiting...")
                    break
                    
                else:
                    print("Invalid choice. Please enter 1-5.")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
    else:
        print("\nRunning in non-interactive mode. Use --help for available options.")

if __name__ == "__main__":
    asyncio.run(main())
