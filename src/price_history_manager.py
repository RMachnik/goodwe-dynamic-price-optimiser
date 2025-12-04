"""
Price History Manager - Tracks historical electricity prices for adaptive threshold calculations.

This module manages a rolling window of electricity prices from the Polish PSE API,
calculates statistical measures (median, mean, percentiles), and persists data
to enable adaptive price thresholds that automatically adjust to seasonal market conditions.
"""

import json
import logging
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from statistics import median, mean

logger = logging.getLogger(__name__)


class PriceHistoryManager:
    """Manages historical price data for adaptive threshold calculations."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize price history manager.
        
        Args:
            config: Configuration dict containing:
                - lookback_days: Days of history to maintain (default: 7)
                - min_samples: Minimum samples required for reliable stats (default: 24)
        """
        self.lookback_days = config.get('lookback_days', 7)
        self.min_samples = config.get('min_samples', 24)
        
        # Calculate maximum cache size: 7 days * 24 hours * 4 (15-min intervals)
        max_cache_size = self.lookback_days * 24 * 4
        self.price_cache = deque(maxlen=max_cache_size)
        
        # Persistence configuration
        self.data_dir = Path('data')
        self.cache_file = self.data_dir / 'price_history.json'
        self.energy_data_dir = Path('out/energy_data')
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load persisted cache on initialization
        self._load_cache()
        
        logger.info(
            f"PriceHistoryManager initialized: "
            f"lookback={self.lookback_days}d, "
            f"min_samples={self.min_samples}, "
            f"cache_size={len(self.price_cache)}"
        )
    
    def add_price_point(self, timestamp: datetime, price_pln: float) -> None:
        """
        Add a price point to the history.
        
        Args:
            timestamp: Timestamp of the price
            price_pln: Price in PLN/kWh
        """
        if price_pln < 0:
            logger.warning(f"Ignoring negative price: {price_pln} PLN/kWh at {timestamp}")
            return
        
        # Store as tuple: (timestamp, price)
        self.price_cache.append((timestamp.isoformat(), price_pln))
        
        # Periodically persist cache (every 10 new points)
        if len(self.price_cache) % 10 == 0:
            self._save_cache()
    
    def get_recent_prices(self, hours: Optional[int] = None) -> List[float]:
        """
        Get prices from the last N hours.
        
        Args:
            hours: Number of hours to look back (default: all available)
        
        Returns:
            List of prices in PLN/kWh
        """
        if hours is None:
            hours = self.lookback_days * 24
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        prices = []
        for timestamp_str, price in self.price_cache:
            timestamp = datetime.fromisoformat(timestamp_str)
            if timestamp >= cutoff_time:
                prices.append(price)
        
        return prices
    
    def calculate_statistics(self) -> Dict[str, float]:
        """
        Calculate statistical measures from recent prices.
        
        Returns:
            Dict containing:
                - median: Median price
                - mean: Mean price
                - p25: 25th percentile
                - p50: 50th percentile (same as median)
                - p75: 75th percentile
                - p90: 90th percentile
                - sample_count: Number of samples used
        """
        prices = self.get_recent_prices()
        
        if not prices:
            logger.warning("No price data available for statistics calculation")
            return {
                'median': 0.0,
                'mean': 0.0,
                'p25': 0.0,
                'p50': 0.0,
                'p75': 0.0,
                'p90': 0.0,
                'sample_count': 0
            }
        
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        
        def percentile(data: List[float], p: float) -> float:
            """Calculate percentile using linear interpolation."""
            if not data:
                return 0.0
            k = (len(data) - 1) * p
            f = int(k)
            c = int(k) + 1
            if c >= len(data):
                return data[-1]
            d0 = data[f] * (c - k)
            d1 = data[c] * (k - f)
            return d0 + d1
        
        stats = {
            'median': median(sorted_prices),
            'mean': mean(sorted_prices),
            'p25': percentile(sorted_prices, 0.25),
            'p50': percentile(sorted_prices, 0.50),
            'p75': percentile(sorted_prices, 0.75),
            'p90': percentile(sorted_prices, 0.90),
            'sample_count': n
        }
        
        logger.debug(
            f"Price statistics: median={stats['median']:.3f}, "
            f"mean={stats['mean']:.3f}, "
            f"p75={stats['p75']:.3f}, "
            f"samples={stats['sample_count']}"
        )
        
        return stats
    
    def load_historical_from_files(self) -> int:
        """
        Bootstrap price history from existing decision files in out/energy_data/.
        
        Returns:
            Number of price points loaded
        """
        if not self.energy_data_dir.exists():
            logger.info(f"Energy data directory not found: {self.energy_data_dir}")
            return 0
        
        loaded_count = 0
        cutoff_time = datetime.now() - timedelta(days=self.lookback_days)
        
        try:
            # Find all JSON files in energy_data directory
            json_files = sorted(self.energy_data_dir.glob('*.json'))
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    # Extract timestamp - all decision files have this
                    if 'timestamp' not in data:
                        continue
                    
                    timestamp = datetime.fromisoformat(data['timestamp'])
                    
                    # Only load recent data within lookback window
                    if timestamp < cutoff_time:
                        continue
                    
                    # Try multiple field names for price (charging vs selling decision files)
                    price = None
                    if 'current_price' in data and data['current_price'] is not None:
                        price = float(data['current_price'])
                    elif 'current_price_pln' in data and data['current_price_pln'] is not None:
                        price = float(data['current_price_pln'])
                    elif 'current_price_pln_kwh' in data and data['current_price_pln_kwh'] is not None:
                        price = float(data['current_price_pln_kwh'])
                    
                    if price is not None and price > 0:
                        self.price_cache.append((timestamp.isoformat(), price))
                        loaded_count += 1
                
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.debug(f"Skipping file {json_file.name}: {e}")
                    continue
            
            if loaded_count > 0:
                logger.info(
                    f"Bootstrapped {loaded_count} price points from {len(json_files)} "
                    f"decision files in {self.energy_data_dir}"
                )
                # Save bootstrapped cache
                self._save_cache()
        
        except Exception as e:
            logger.error(f"Failed to bootstrap price history from files: {e}")
        
        return loaded_count
    
    def _save_cache(self) -> None:
        """Persist price cache to JSON file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(list(self.price_cache), f, indent=2)
            logger.debug(f"Saved {len(self.price_cache)} price points to {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to save price cache: {e}")
    
    def _load_cache(self) -> None:
        """Load persisted price cache from JSON file."""
        if not self.cache_file.exists():
            logger.debug(f"No existing cache file found at {self.cache_file}")
            return
        
        try:
            with open(self.cache_file, 'r') as f:
                cached_data = json.load(f)
            
            # Filter out old data beyond lookback window
            cutoff_time = datetime.now() - timedelta(days=self.lookback_days)
            
            for timestamp_str, price in cached_data:
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp >= cutoff_time:
                    self.price_cache.append((timestamp_str, price))
            
            logger.info(f"Loaded {len(self.price_cache)} price points from cache")
        
        except Exception as e:
            logger.error(f"Failed to load price cache: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the current cache state.
        
        Returns:
            Dict with cache statistics
        """
        if not self.price_cache:
            return {
                'count': 0,
                'oldest': None,
                'newest': None,
                'coverage_hours': 0
            }
        
        oldest_ts = datetime.fromisoformat(self.price_cache[0][0])
        newest_ts = datetime.fromisoformat(self.price_cache[-1][0])
        coverage_hours = (newest_ts - oldest_ts).total_seconds() / 3600
        
        return {
            'count': len(self.price_cache),
            'oldest': oldest_ts.isoformat(),
            'newest': newest_ts.isoformat(),
            'coverage_hours': coverage_hours
        }
