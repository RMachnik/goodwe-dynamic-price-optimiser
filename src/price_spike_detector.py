#!/usr/bin/env python3
"""
Price Spike Detector

Monitors real-time electricity prices for sudden spikes and extreme peaks
to enable immediate selling decisions without waiting for forecast analysis.

Phase 4 Feature: Real-Time Price Spike Detection
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum
from collections import deque


class SpikeLevel(Enum):
    """Classification of price spikes"""
    NONE = "none"          # No spike detected
    MODERATE = "moderate"  # 15-30% increase
    HIGH = "high"          # 30-50% increase
    EXTREME = "extreme"    # >50% increase or >1.5 PLN/kWh


@dataclass
class PriceSpike:
    """Details of detected price spike"""
    spike_level: SpikeLevel
    current_price: float
    previous_price: float
    percent_increase: float
    detection_time: datetime
    confidence: float
    reasoning: str
    recommended_action: str


class PriceSpikeDetector:
    """
    Detects price spikes in real-time for immediate selling decisions
    
    Features:
    - Real-time price monitoring
    - Spike classification (moderate, high, extreme)
    - Historical price comparison
    - Confidence scoring based on price history
    - Immediate action recommendations
    """
    
    def __init__(self, config: Dict):
        """Initialize price spike detector"""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Spike detection configuration
        spike_config = config.get('battery_selling', {}).get('smart_timing', {}).get('spike_detection', {})
        self.enabled = spike_config.get('enabled', True)
        
        # Spike thresholds
        self.moderate_spike_percent = spike_config.get('moderate_spike_percent', 15)
        self.high_spike_percent = spike_config.get('high_spike_percent', 30)
        self.extreme_spike_percent = spike_config.get('extreme_spike_percent', 50)
        self.critical_price_threshold = spike_config.get('critical_price_threshold', 1.5)
        
        # Detection parameters
        self.min_price_samples = spike_config.get('min_price_samples', 3)
        self.lookback_minutes = spike_config.get('lookback_minutes', 60)
        self.min_confidence_threshold = spike_config.get('min_confidence_threshold', 0.7)
        
        # Price history buffer (stores recent prices for spike detection)
        self.price_history = deque(maxlen=100)  # Last 100 price samples
        
        # Spike tracking
        self.last_spike = None
        self.spike_count_today = 0
        self.last_reset = datetime.now().date()
        
        self.logger.info(f"Price Spike Detector initialized: "
                        f"moderate={self.moderate_spike_percent}%, "
                        f"high={self.high_spike_percent}%, "
                        f"extreme={self.extreme_spike_percent}%, "
                        f"critical={self.critical_price_threshold} PLN/kWh")
    
    def add_price_sample(self, price: float, timestamp: Optional[datetime] = None) -> None:
        """
        Add a price sample to history
        
        Args:
            price: Current electricity price (PLN/kWh)
            timestamp: Sample timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.price_history.append({
            'price': price,
            'timestamp': timestamp
        })
        
        # Reset daily spike counter at midnight
        today = datetime.now().date()
        if today != self.last_reset:
            self.spike_count_today = 0
            self.last_reset = today
    
    def detect_spike(self, current_price: float) -> Optional[PriceSpike]:
        """
        Detect if current price represents a spike
        
        Args:
            current_price: Current electricity price (PLN/kWh)
            
        Returns:
            PriceSpike object if spike detected, None otherwise
        """
        if not self.enabled:
            return None
        
        # Add current price to history
        self.add_price_sample(current_price)
        
        # Need minimum samples for spike detection
        if len(self.price_history) < self.min_price_samples:
            self.logger.debug(f"Insufficient price history: {len(self.price_history)}/{self.min_price_samples}")
            return None
        
        # Get reference price (average of recent prices, excluding current)
        reference_price = self._calculate_reference_price()
        
        if reference_price <= 0:
            return None
        
        # Calculate percent increase
        percent_increase = ((current_price - reference_price) / reference_price) * 100
        
        # Determine spike level
        spike_level = self._classify_spike(current_price, percent_increase)
        
        if spike_level == SpikeLevel.NONE:
            return None
        
        # Calculate confidence
        confidence = self._calculate_confidence(current_price, reference_price)
        
        # Generate spike object
        spike = PriceSpike(
            spike_level=spike_level,
            current_price=current_price,
            previous_price=reference_price,
            percent_increase=percent_increase,
            detection_time=datetime.now(),
            confidence=confidence,
            reasoning=self._generate_reasoning(spike_level, current_price, reference_price, percent_increase),
            recommended_action=self._recommend_action(spike_level, current_price, confidence)
        )
        
        # Update tracking
        self.last_spike = spike
        self.spike_count_today += 1
        
        self.logger.info(f"⚠️ SPIKE DETECTED: {spike_level.value.upper()} - "
                        f"{current_price:.3f} PLN/kWh (+{percent_increase:.1f}%) "
                        f"confidence={confidence:.2f}")
        
        return spike
    
    def _calculate_reference_price(self) -> float:
        """
        Calculate reference price from recent history
        
        Uses median of last N minutes to avoid outliers
        """
        if not self.price_history:
            return 0.0
        
        # Get prices from lookback window
        cutoff_time = datetime.now() - timedelta(minutes=self.lookback_minutes)
        recent_prices = [
            sample['price']
            for sample in self.price_history
            if sample['timestamp'] >= cutoff_time
        ]
        
        if len(recent_prices) < 2:
            # Not enough data, use all available
            recent_prices = [sample['price'] for sample in self.price_history]
        
        # Use median to avoid spike contamination
        recent_prices.sort()
        mid = len(recent_prices) // 2
        
        if len(recent_prices) % 2 == 0:
            # Even number: average of two middle values
            reference = (recent_prices[mid-1] + recent_prices[mid]) / 2
        else:
            # Odd number: middle value
            reference = recent_prices[mid]
        
        return reference
    
    def _classify_spike(self, current_price: float, percent_increase: float) -> SpikeLevel:
        """
        Classify spike level based on increase and absolute price
        
        Args:
            current_price: Current price (PLN/kWh)
            percent_increase: Percentage increase from reference
            
        Returns:
            SpikeLevel classification
        """
        # Rule 1: Critical absolute price (regardless of increase)
        if current_price >= self.critical_price_threshold:
            return SpikeLevel.EXTREME
        
        # Rule 2: Percentage-based classification
        if percent_increase >= self.extreme_spike_percent:
            return SpikeLevel.EXTREME
        elif percent_increase >= self.high_spike_percent:
            return SpikeLevel.HIGH
        elif percent_increase >= self.moderate_spike_percent:
            return SpikeLevel.MODERATE
        else:
            return SpikeLevel.NONE
    
    def _calculate_confidence(self, current_price: float, reference_price: float) -> float:
        """
        Calculate confidence in spike detection
        
        Higher confidence when:
        - More price samples available
        - Stable reference price (low variance)
        - Larger price increase
        """
        # Factor 1: Sample size (more samples = higher confidence)
        sample_factor = min(len(self.price_history) / 20, 1.0)  # Max at 20 samples
        
        # Factor 2: Price increase magnitude (larger increase = higher confidence)
        increase_ratio = current_price / reference_price if reference_price > 0 else 1.0
        increase_factor = min((increase_ratio - 1.0) / 0.5, 1.0)  # Max at 50% increase
        
        # Factor 3: Price history variance (lower variance = higher confidence)
        variance_factor = self._calculate_variance_factor()
        
        # Weighted average
        confidence = (sample_factor * 0.3 +
                     increase_factor * 0.5 +
                     variance_factor * 0.2)
        
        return max(0.0, min(1.0, confidence))
    
    def _calculate_variance_factor(self) -> float:
        """Calculate confidence factor based on price history variance"""
        if len(self.price_history) < 3:
            return 0.5  # Medium confidence with limited data
        
        prices = [sample['price'] for sample in list(self.price_history)[-10:]]
        
        # Calculate standard deviation
        mean_price = sum(prices) / len(prices)
        variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5
        
        # Lower variance = higher confidence
        # Assume std_dev of 0.1 PLN/kWh or less is stable
        if std_dev <= 0.05:
            return 1.0  # Very stable
        elif std_dev <= 0.10:
            return 0.8  # Stable
        elif std_dev <= 0.20:
            return 0.6  # Moderate
        else:
            return 0.4  # Volatile
    
    def _generate_reasoning(
        self,
        spike_level: SpikeLevel,
        current_price: float,
        reference_price: float,
        percent_increase: float
    ) -> str:
        """Generate human-readable reasoning for spike detection"""
        
        if spike_level == SpikeLevel.EXTREME:
            if current_price >= self.critical_price_threshold:
                return (f"EXTREME spike: Price {current_price:.3f} PLN/kWh exceeds critical threshold "
                       f"{self.critical_price_threshold} PLN/kWh (from {reference_price:.3f})")
            else:
                return (f"EXTREME spike: Price jumped {percent_increase:.1f}% "
                       f"from {reference_price:.3f} to {current_price:.3f} PLN/kWh")
        
        elif spike_level == SpikeLevel.HIGH:
            return (f"HIGH spike: Price increased {percent_increase:.1f}% "
                   f"from {reference_price:.3f} to {current_price:.3f} PLN/kWh")
        
        elif spike_level == SpikeLevel.MODERATE:
            return (f"MODERATE spike: Price rose {percent_increase:.1f}% "
                   f"from {reference_price:.3f} to {current_price:.3f} PLN/kWh")
        
        else:
            return f"No significant spike detected"
    
    def _recommend_action(self, spike_level: SpikeLevel, current_price: float, confidence: float) -> str:
        """Recommend action based on spike level"""
        
        if spike_level == SpikeLevel.EXTREME:
            return "SELL IMMEDIATELY - Extreme price spike detected"
        
        elif spike_level == SpikeLevel.HIGH:
            if confidence >= 0.8:
                return "SELL NOW - High confidence spike, excellent opportunity"
            else:
                return "CONSIDER SELLING - High spike but lower confidence"
        
        elif spike_level == SpikeLevel.MODERATE:
            if confidence >= 0.7:
                return "EVALUATE SELLING - Moderate spike, check forecast for better peak"
            else:
                return "MONITOR - Moderate spike but uncertain, wait for confirmation"
        
        else:
            return "NO ACTION - Price within normal range"
    
    def is_spike_active(self, max_age_minutes: int = 5) -> bool:
        """
        Check if there's an active spike within the last N minutes
        
        Args:
            max_age_minutes: Maximum age of spike to consider active
            
        Returns:
            True if spike is still active
        """
        if not self.last_spike:
            return False
        
        age = (datetime.now() - self.last_spike.detection_time).total_seconds() / 60
        return age <= max_age_minutes
    
    def get_spike_statistics(self) -> Dict[str, Any]:
        """Get spike detection statistics for monitoring"""
        return {
            'enabled': self.enabled,
            'samples_collected': len(self.price_history),
            'spikes_today': self.spike_count_today,
            'last_spike': {
                'level': self.last_spike.spike_level.value if self.last_spike else None,
                'price': self.last_spike.current_price if self.last_spike else None,
                'time': self.last_spike.detection_time.isoformat() if self.last_spike else None,
                'confidence': self.last_spike.confidence if self.last_spike else None
            } if self.last_spike else None,
            'current_reference_price': self._calculate_reference_price() if self.price_history else None
        }
    
    def clear_history(self) -> None:
        """Clear price history (useful for testing)"""
        self.price_history.clear()
        self.last_spike = None

