"""
Adaptive Threshold Calculator - Calculates price thresholds based on market conditions.

This module calculates adaptive price thresholds using multiplier-based or percentile-based
methods, with seasonal adjustments to track Polish electricity market variations.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class AdaptiveThresholdCalculator:
    """Calculate adaptive price thresholds based on market conditions and seasons."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adaptive threshold calculator.
        
        Args:
            config: Configuration dict containing:
                - method: 'multiplier' or 'percentile'
                - high_price_multiplier: Multiplier for high price threshold
                - critical_price_multiplier: Multiplier for critical charging threshold
                - high_price_percentile: Percentile for high price (if method='percentile')
                - critical_price_percentile: Percentile for critical (if method='percentile')
                - seasonal_adjustments_enabled: Enable seasonal multipliers
                - seasonal_multipliers: Dict with winter/summer/spring_autumn config
                - fallback_high_price_pln: Fallback value when insufficient data
                - fallback_critical_price_pln: Fallback value when insufficient data
        """
        # Calculation method
        self.method = config.get('method', 'multiplier')
        
        # Multiplier-based configuration
        self.high_price_multiplier = config.get('high_price_multiplier', 1.5)
        self.critical_price_multiplier = config.get('critical_price_multiplier', 1.3)
        
        # Percentile-based configuration
        self.high_price_percentile = config.get('high_price_percentile', 75)
        self.critical_price_percentile = config.get('critical_price_percentile', 65)
        
        # Seasonal adjustments
        self.seasonal_enabled = config.get('seasonal_adjustments_enabled', True)
        self.seasonal_multipliers = config.get('seasonal_multipliers', {})
        
        # Fallback values
        self.fallback_high_price = config.get('fallback_high_price_pln', 1.35)
        self.fallback_critical_price = config.get('fallback_critical_price_pln', 1.20)
        
        logger.info(
            f"AdaptiveThresholdCalculator initialized: "
            f"method={self.method}, "
            f"high_multiplier={self.high_price_multiplier}, "
            f"critical_multiplier={self.critical_price_multiplier}, "
            f"seasonal={self.seasonal_enabled}"
        )
    
    def calculate_high_price_threshold(
        self, 
        price_stats: Dict[str, float],
        current_time: Optional[datetime] = None
    ) -> float:
        """
        Calculate adaptive high price threshold.
        
        Args:
            price_stats: Price statistics dict with 'median', 'mean', 'p75', etc.
            current_time: Current datetime for seasonal adjustment (default: now)
        
        Returns:
            High price threshold in PLN/kWh
        """
        if current_time is None:
            current_time = datetime.now()
        
        # Check if we have sufficient data
        if price_stats.get('sample_count', 0) == 0:
            logger.warning(
                f"No price data available, using fallback high price threshold: "
                f"{self.fallback_high_price:.3f} PLN/kWh"
            )
            return self.fallback_high_price
        
        # Calculate base threshold using selected method
        if self.method == 'percentile':
            # Use percentile directly from stats
            base_threshold = price_stats.get('p75', price_stats.get('median', 0))
            if base_threshold == 0:
                logger.warning("Percentile data unavailable, using fallback")
                return self.fallback_high_price
        else:  # multiplier method
            median = price_stats.get('median', 0)
            if median == 0:
                logger.warning("Median price is zero, using fallback")
                return self.fallback_high_price
            base_threshold = median * self.high_price_multiplier
        
        # Apply seasonal adjustment
        if self.seasonal_enabled:
            seasonal_multiplier = self._get_seasonal_multiplier(current_time)
            threshold = base_threshold * seasonal_multiplier
            
            logger.debug(
                f"High price threshold: base={base_threshold:.3f}, "
                f"seasonal={seasonal_multiplier:.2f}x, "
                f"final={threshold:.3f} PLN/kWh"
            )
        else:
            threshold = base_threshold
        
        return threshold
    
    def calculate_critical_price_threshold(
        self, 
        price_stats: Dict[str, float],
        current_time: Optional[datetime] = None
    ) -> float:
        """
        Calculate adaptive critical charging price threshold.
        
        Args:
            price_stats: Price statistics dict with 'median', 'mean', 'p65', etc.
            current_time: Current datetime for seasonal adjustment (default: now)
        
        Returns:
            Critical price threshold in PLN/kWh
        """
        if current_time is None:
            current_time = datetime.now()
        
        # Check if we have sufficient data
        if price_stats.get('sample_count', 0) == 0:
            logger.warning(
                f"No price data available, using fallback critical price threshold: "
                f"{self.fallback_critical_price:.3f} PLN/kWh"
            )
            return self.fallback_critical_price
        
        # Calculate base threshold using selected method
        if self.method == 'percentile':
            # For critical threshold, use lower percentile (more conservative)
            # If p65 not available, calculate from sorted prices or use median
            base_threshold = price_stats.get('p50', price_stats.get('median', 0))
            if base_threshold == 0:
                logger.warning("Percentile data unavailable, using fallback")
                return self.fallback_critical_price
        else:  # multiplier method
            median = price_stats.get('median', 0)
            if median == 0:
                logger.warning("Median price is zero, using fallback")
                return self.fallback_critical_price
            base_threshold = median * self.critical_price_multiplier
        
        # Apply seasonal adjustment
        if self.seasonal_enabled:
            seasonal_multiplier = self._get_seasonal_multiplier(current_time)
            threshold = base_threshold * seasonal_multiplier
            
            logger.debug(
                f"Critical price threshold: base={base_threshold:.3f}, "
                f"seasonal={seasonal_multiplier:.2f}x, "
                f"final={threshold:.3f} PLN/kWh"
            )
        else:
            threshold = base_threshold
        
        return threshold
    
    def _get_seasonal_multiplier(self, current_time: datetime) -> float:
        """
        Get seasonal multiplier based on current date.
        
        Args:
            current_time: Current datetime
        
        Returns:
            Seasonal multiplier (e.g., 1.3 for winter, 0.85 for summer)
        """
        current_month = current_time.month
        
        # Check each season configuration
        for season_name, season_config in self.seasonal_multipliers.items():
            months = season_config.get('months', [])
            if current_month in months:
                multiplier = season_config.get('multiplier', 1.0)
                logger.debug(f"Current season: {season_name}, multiplier: {multiplier}")
                return multiplier
        
        # Default to 1.0 if no season matches
        logger.debug(f"No season match for month {current_month}, using multiplier 1.0")
        return 1.0
    
    def get_season_name(self, current_time: Optional[datetime] = None) -> str:
        """
        Get current season name.
        
        Args:
            current_time: Current datetime (default: now)
        
        Returns:
            Season name (e.g., 'winter', 'summer', 'spring_autumn')
        """
        if current_time is None:
            current_time = datetime.now()
        
        current_month = current_time.month
        
        for season_name, season_config in self.seasonal_multipliers.items():
            months = season_config.get('months', [])
            if current_month in months:
                return season_name
        
        return 'unknown'
    
    def get_calculation_info(self, price_stats: Dict[str, float]) -> Dict[str, Any]:
        """
        Get detailed information about threshold calculations.
        
        Args:
            price_stats: Price statistics dict
        
        Returns:
            Dict with calculation details
        """
        current_time = datetime.now()
        season_name = self.get_season_name(current_time)
        seasonal_multiplier = self._get_seasonal_multiplier(current_time)
        
        high_threshold = self.calculate_high_price_threshold(price_stats, current_time)
        critical_threshold = self.calculate_critical_price_threshold(price_stats, current_time)
        
        return {
            'method': self.method,
            'season': season_name,
            'seasonal_multiplier': seasonal_multiplier,
            'high_price_threshold_pln': high_threshold,
            'critical_price_threshold_pln': critical_threshold,
            'base_median_pln': price_stats.get('median', 0),
            'sample_count': price_stats.get('sample_count', 0),
            'using_fallback': price_stats.get('sample_count', 0) == 0
        }
