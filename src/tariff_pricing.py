#!/usr/bin/env python3
"""
Tariff-based distribution pricing for Polish electricity market.
Handles different tariff types: G11, G12, G12as, G12w, G13, G14dynamic.

This module provides accurate electricity pricing by combining:
- Market price (from CSDAC API)
- SC component (Składnik cenotwórczy) - fixed 0.0892 PLN/kWh
- Distribution price (variable by tariff type)

Final Price = Market Price + SC Component + Distribution Price
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PriceComponents:
    """Breakdown of electricity price components."""
    market_price: float  # PLN/kWh from CSDAC
    sc_component: float  # PLN/kWh (Składnik cenotwórczy)
    distribution_price: float  # PLN/kWh (variable by tariff)
    final_price: float  # PLN/kWh (sum of all)
    tariff_type: str
    timestamp: datetime


class TariffPricingCalculator:
    """Calculate electricity prices based on tariff configuration."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize tariff pricing calculator.
        
        Args:
            config: Full system configuration dict
        """
        tariff_config = config.get('electricity_tariff', {})
        self.tariff_type = tariff_config.get('tariff_type', 'g12w')
        self.sc_component = tariff_config.get('sc_component_pln_kwh', 0.0892)
        self.distribution_config = tariff_config.get('distribution_pricing', {})
        
        logger.info(f"Tariff Pricing Calculator initialized: tariff={self.tariff_type}, SC={self.sc_component} PLN/kWh")
    
    def calculate_final_price(
        self,
        market_price_pln_kwh: float,
        timestamp: datetime,
        kompas_status: Optional[str] = None
    ) -> PriceComponents:
        """
        Calculate final electricity price with all components.
        
        Args:
            market_price_pln_kwh: Market price in PLN/kWh from CSDAC API
            timestamp: Time for the price (used for time-based tariffs)
            kompas_status: Kompas status for G14dynamic (NORMAL USAGE, etc.)
        
        Returns:
            PriceComponents with detailed breakdown
        """
        distribution_price = self._get_distribution_price(timestamp, kompas_status)
        final_price = market_price_pln_kwh + self.sc_component + distribution_price
        
        return PriceComponents(
            market_price=market_price_pln_kwh,
            sc_component=self.sc_component,
            distribution_price=distribution_price,
            final_price=final_price,
            tariff_type=self.tariff_type,
            timestamp=timestamp
        )
    
    def _get_distribution_price(
        self,
        timestamp: datetime,
        kompas_status: Optional[str] = None
    ) -> float:
        """
        Get distribution price based on tariff type.
        
        Args:
            timestamp: Time for the price
            kompas_status: Kompas status (for G14dynamic)
        
        Returns:
            Distribution price in PLN/kWh
        """
        config = self.distribution_config.get(self.tariff_type, {})
        tariff_type = config.get('type', 'static')
        
        if tariff_type == 'static':
            return config.get('price', 0.0)
        
        elif tariff_type == 'time_based':
            return self._get_time_based_price(timestamp, config)
        
        elif tariff_type == 'kompas_based':
            return self._get_kompas_based_price(kompas_status, config)
        
        else:
            logger.warning(f"Unknown tariff type: {tariff_type}, returning 0.0")
            return 0.0
    
    def _get_time_based_price(self, timestamp: datetime, config: Dict) -> float:
        """
        Get price for time-based tariffs (G12, G12w, G12as).
        
        Args:
            timestamp: Time to check
            config: Tariff configuration
        
        Returns:
            Distribution price for the time period
        """
        peak_hours = config.get('peak_hours', {})
        start_hour = peak_hours.get('start', 6)
        end_hour = peak_hours.get('end', 22)
        
        hour = timestamp.hour
        is_peak = start_hour <= hour < end_hour
        
        prices = config.get('prices', {})
        price = prices.get('peak' if is_peak else 'off_peak', 0.0)
        
        return price
    
    def _get_kompas_based_price(
        self,
        kompas_status: Optional[str],
        config: Dict
    ) -> float:
        """
        Get price for kompas-based tariff (G14dynamic).
        
        Args:
            kompas_status: Kompas status string
            config: Tariff configuration
        
        Returns:
            Distribution price based on grid status
        """
        if not kompas_status:
            fallback = config.get('fallback_price', 0.0578)
            logger.debug(f"No kompas status provided, using fallback: {fallback} PLN/kWh")
            return fallback
        
        prices = config.get('prices', {})
        
        # Map kompas status labels to config keys
        status_map = {
            'NORMAL USAGE': 'normal_usage',
            'RECOMMENDED USAGE': 'recommended_usage',
            'RECOMMENDED SAVING': 'recommended_saving',
            'REQUIRED REDUCTION': 'required_reduction'
        }
        
        price_key = status_map.get(kompas_status)
        if price_key:
            price = prices.get(price_key, config.get('fallback_price', 0.0578))
            logger.debug(f"Kompas status '{kompas_status}' → {price} PLN/kWh")
            return price
        
        # Unknown status - use fallback
        fallback = config.get('fallback_price', 0.0578)
        logger.warning(f"Unknown kompas status: '{kompas_status}', using fallback: {fallback} PLN/kWh")
        return fallback
    
    def get_tariff_info(self) -> Dict[str, Any]:
        """Get current tariff configuration info."""
        config = self.distribution_config.get(self.tariff_type, {})
        return {
            'tariff_type': self.tariff_type,
            'sc_component': self.sc_component,
            'distribution_type': config.get('type', 'unknown'),
            'config': config
        }

