#!/usr/bin/env python3
"""
Test suite for PV vs Consumption Analysis Module
Tests the intelligent analysis of PV production vs house consumption for optimal charging decisions
"""

import unittest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pv_consumption_analyzer import PVConsumptionAnalyzer, PowerBalance, ChargingRecommendation

class TestPVConsumptionAnalyzer(unittest.TestCase):
    """Test cases for PV vs Consumption Analyzer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'timing_awareness': {
                'battery_capacity_kwh': 10.0,
                'charging_rate_kw': 3.0,
                'pv_capacity_kw': 10.0
            },
            'pv_consumption_analysis': {
                'pv_overproduction_threshold_w': 500,
                'consumption_forecast_hours': 4,
                'historical_data_days': 7
            },
            'electricity_pricing': {
                'sc_component_pln_kwh': 0.0892
            }
        }
        self.analyzer = PVConsumptionAnalyzer(self.config)
    
    def test_initialization(self):
        """Test PV consumption analyzer initialization"""
        self.assertEqual(self.analyzer.battery_capacity_kwh, 10.0)
        self.assertEqual(self.analyzer.charging_rate_kw, 3.0)
        self.assertEqual(self.analyzer.pv_capacity_kw, 10.0)
        self.assertEqual(self.analyzer.pv_overproduction_threshold_w, 500)
        self.assertEqual(self.analyzer.consumption_forecast_hours, 4)
        self.assertEqual(self.analyzer.max_history_days, 7)
    
    def test_analyze_power_balance(self):
        """Test power balance analysis"""
        current_data = {
            'photovoltaic': {'current_power_w': 2000},
            'consumption': {'current_power_w': 1500},
            'battery': {'current_power_w': 0},
            'grid': {'current_power_w': -500}
        }
        
        power_balance = self.analyzer.analyze_power_balance(current_data)
        
        self.assertEqual(power_balance.pv_power_w, 2000)
        self.assertEqual(power_balance.consumption_power_w, 1500)
        self.assertEqual(power_balance.net_power_w, 500)  # 2000 - 1500
        self.assertEqual(power_balance.battery_power_w, 0)
        self.assertEqual(power_balance.grid_power_w, -500)
        self.assertIsInstance(power_balance.timestamp, datetime)
        self.assertGreater(power_balance.confidence, 0)
    
    def test_should_charge_from_pv_excess_pv(self):
        """Test PV charging decision with excess PV"""
        power_balance = PowerBalance(
            pv_power_w=2000,
            consumption_power_w=1000,
            net_power_w=1000,  # Excess PV
            battery_power_w=0,
            grid_power_w=0,
            timestamp=datetime.now(),
            confidence=0.9
        )
        
        result = self.analyzer.should_charge_from_pv(power_balance, 50.0)
        self.assertTrue(result)
    
    def test_should_charge_from_pv_insufficient_pv(self):
        """Test PV charging decision with insufficient PV"""
        power_balance = PowerBalance(
            pv_power_w=1000,
            consumption_power_w=1500,
            net_power_w=-500,  # Deficit
            battery_power_w=0,
            grid_power_w=500,
            timestamp=datetime.now(),
            confidence=0.9
        )
        
        result = self.analyzer.should_charge_from_pv(power_balance, 50.0)
        self.assertFalse(result)
    
    def test_should_charge_from_pv_full_battery(self):
        """Test PV charging decision with full battery"""
        power_balance = PowerBalance(
            pv_power_w=2000,
            consumption_power_w=1000,
            net_power_w=1000,  # Excess PV
            battery_power_w=0,
            grid_power_w=0,
            timestamp=datetime.now(),
            confidence=0.9
        )
        
        result = self.analyzer.should_charge_from_pv(power_balance, 95.0)
        self.assertFalse(result)
    
    def test_should_charge_from_grid_low_price(self):
        """Test grid charging decision in low price window"""
        power_balance = PowerBalance(
            pv_power_w=1000,
            consumption_power_w=1500,
            net_power_w=-500,  # Deficit
            battery_power_w=0,
            grid_power_w=500,
            timestamp=datetime.now(),
            confidence=0.9
        )
        
        # Mock low price data
        price_data = {
            'value': [
                {'dtime': '2025-01-01 12:00', 'csdac_pln': '100'},  # Low price
                {'dtime': '2025-01-01 12:15', 'csdac_pln': '120'},
                {'dtime': '2025-01-01 12:30', 'csdac_pln': '150'},
                {'dtime': '2025-01-01 12:45', 'csdac_pln': '200'}
            ]
        }
        
        with patch.object(self.analyzer, '_is_low_price_window', return_value=True):
            result = self.analyzer.should_charge_from_grid(power_balance, 50.0, price_data)
            self.assertTrue(result)
    
    def test_should_charge_from_grid_high_price(self):
        """Test grid charging decision in high price window"""
        power_balance = PowerBalance(
            pv_power_w=1000,
            consumption_power_w=1500,
            net_power_w=-500,  # Deficit
            battery_power_w=0,
            grid_power_w=500,
            timestamp=datetime.now(),
            confidence=0.9
        )
        
        price_data = {'value': []}
        
        with patch.object(self.analyzer, '_is_low_price_window', return_value=False):
            result = self.analyzer.should_charge_from_grid(power_balance, 50.0, price_data)
            self.assertFalse(result)
    
    def test_analyze_charging_timing_sufficient_pv(self):
        """Test charging timing analysis with sufficient PV"""
        power_balance = PowerBalance(
            pv_power_w=2000,
            consumption_power_w=1000,
            net_power_w=1000,
            battery_power_w=0,
            grid_power_w=0,
            timestamp=datetime.now(),
            confidence=0.9
        )
        
        # Mock PV forecast with sufficient energy
        pv_forecast = [
            {'forecasted_power_kw': 2.0, 'timestamp': '2025-01-01 12:00'},
            {'forecasted_power_kw': 2.0, 'timestamp': '2025-01-01 12:15'},
            {'forecasted_power_kw': 2.0, 'timestamp': '2025-01-01 12:30'},
            {'forecasted_power_kw': 2.0, 'timestamp': '2025-01-01 12:45'}
        ]
        
        price_data = {'value': []}
        
        recommendation = self.analyzer.analyze_charging_timing(
            power_balance, 30.0, pv_forecast, price_data
        )
        
        # The recommendation should suggest charging if PV is available
        self.assertIn(recommendation.charging_source, ['pv', 'hybrid'])
        self.assertGreater(recommendation.energy_needed_kwh, 0)
        self.assertGreaterEqual(recommendation.pv_available_kwh, 0)
    
    def test_analyze_charging_timing_hybrid_charging(self):
        """Test charging timing analysis with hybrid charging"""
        power_balance = PowerBalance(
            pv_power_w=1000,
            consumption_power_w=1500,
            net_power_w=-500,
            battery_power_w=0,
            grid_power_w=500,
            timestamp=datetime.now(),
            confidence=0.9
        )
        
        # Mock PV forecast with limited energy
        pv_forecast = [
            {'forecasted_power_kw': 1.0, 'timestamp': '2025-01-01 12:00'},
            {'forecasted_power_kw': 1.0, 'timestamp': '2025-01-01 12:15'}
        ]
        
        price_data = {'value': []}
        
        with patch.object(self.analyzer, '_is_low_price_window', return_value=True), \
             patch.object(self.analyzer, '_get_price_window_duration', return_value=2.0):
            
            recommendation = self.analyzer.analyze_charging_timing(
                power_balance, 30.0, pv_forecast, price_data
            )
            
            self.assertTrue(recommendation.should_charge)
            self.assertEqual(recommendation.charging_source, 'hybrid')
            self.assertEqual(recommendation.priority, 'critical')
            self.assertGreater(recommendation.pv_available_kwh, 0)
            self.assertGreater(recommendation.grid_needed_kwh, 0)
    
    def test_analyze_charging_timing_wait(self):
        """Test charging timing analysis - wait for better conditions"""
        power_balance = PowerBalance(
            pv_power_w=1000,
            consumption_power_w=1500,
            net_power_w=-500,
            battery_power_w=0,
            grid_power_w=500,
            timestamp=datetime.now(),
            confidence=0.9
        )
        
        # Mock PV forecast with limited energy
        pv_forecast = [
            {'forecasted_power_kw': 0.5, 'timestamp': '2025-01-01 12:00'}
        ]
        
        price_data = {'value': []}
        
        with patch.object(self.analyzer, '_is_low_price_window', return_value=False):
            recommendation = self.analyzer.analyze_charging_timing(
                power_balance, 30.0, pv_forecast, price_data
            )
            
            self.assertFalse(recommendation.should_charge)
            self.assertEqual(recommendation.charging_source, 'pv')
            self.assertEqual(recommendation.priority, 'medium')
    
    def test_forecast_consumption(self):
        """Test consumption forecasting"""
        # Add some historical data
        self.analyzer.consumption_history = [
            {'timestamp': datetime.now() - timedelta(hours=1), 'consumption_w': 1500, 'hour': 11},
            {'timestamp': datetime.now() - timedelta(hours=2), 'consumption_w': 1200, 'hour': 10},
            {'timestamp': datetime.now() - timedelta(days=1), 'consumption_w': 1400, 'hour': 12},
            {'timestamp': datetime.now() - timedelta(days=1, hours=1), 'consumption_w': 1600, 'hour': 11}
        ]
        
        forecasts = self.analyzer.forecast_consumption(hours_ahead=2)
        
        self.assertEqual(len(forecasts), 2)
        self.assertIn('timestamp', forecasts[0])
        self.assertIn('forecasted_consumption_w', forecasts[0])
        self.assertIn('confidence', forecasts[0])
        self.assertIn('method', forecasts[0])
    
    def test_update_consumption_history(self):
        """Test consumption history update"""
        current_data = {
            'consumption': {'current_power_w': 1500}
        }
        
        initial_count = len(self.analyzer.consumption_history)
        self.analyzer.update_consumption_history(current_data)
        
        self.assertEqual(len(self.analyzer.consumption_history), initial_count + 1)
        self.assertEqual(self.analyzer.consumption_history[-1]['consumption_w'], 1500)
    
    def test_calculate_data_confidence(self):
        """Test data confidence calculation"""
        # Test with complete data
        complete_data = {
            'photovoltaic': {'current_power_w': 2000},
            'consumption': {'current_power_w': 1500},
            'battery': {'soc_percent': 60},
            'grid': {'current_power_w': -500}
        }
        
        confidence = self.analyzer._calculate_data_confidence(complete_data)
        self.assertEqual(confidence, 1.0)
        
        # Test with partial data
        partial_data = {
            'photovoltaic': {'current_power_w': 2000},
            'consumption': {'current_power_w': 0}  # No consumption data
        }
        
        confidence = self.analyzer._calculate_data_confidence(partial_data)
        self.assertEqual(confidence, 0.5)  # Only PV data (0.3 for PV + 0.2 for consumption=0)
    
    def test_is_low_price_window(self):
        """Test low price window detection"""
        price_data = {
            'value': [
                {'dtime': '2025-01-01 12:00', 'csdac_pln': '100'},  # Low price
                {'dtime': '2025-01-01 12:15', 'csdac_pln': '120'},
                {'dtime': '2025-01-01 12:30', 'csdac_pln': '150'},
                {'dtime': '2025-01-01 12:45', 'csdac_pln': '200'},
                {'dtime': '2025-01-01 13:00', 'csdac_pln': '250'},
                {'dtime': '2025-01-01 13:15', 'csdac_pln': '300'},
                {'dtime': '2025-01-01 13:30', 'csdac_pln': '350'},
                {'dtime': '2025-01-01 13:45', 'csdac_pln': '400'}
            ]
        }
        
        with patch('pv_consumption_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0)
            mock_datetime.strptime = datetime.strptime
            
            result = self.analyzer._is_low_price_window(price_data)
            self.assertTrue(result)  # 100 PLN/MWh should be low
    
    def test_get_price_window_duration(self):
        """Test price window duration calculation"""
        price_data = {
            'value': [
                {'dtime': '2025-01-01 12:00', 'csdac_pln': '100'},  # Low price
                {'dtime': '2025-01-01 12:15', 'csdac_pln': '120'},  # Low price
                {'dtime': '2025-01-01 12:30', 'csdac_pln': '150'},  # Low price
                {'dtime': '2025-01-01 12:45', 'csdac_pln': '200'},  # High price
                {'dtime': '2025-01-01 13:00', 'csdac_pln': '250'}
            ]
        }
        
        with patch('pv_consumption_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0)
            mock_datetime.strptime = datetime.strptime
            
            duration = self.analyzer._get_price_window_duration(price_data)
            self.assertEqual(duration, 0.5)  # 2 * 0.25 hours = 30 minutes (stops at first high price)
    
    def test_calculate_pv_availability(self):
        """Test PV availability calculation"""
        pv_forecast = [
            {'forecasted_power_kw': 2.0, 'timestamp': '2025-01-01 12:00'},
            {'forecasted_power_kw': 2.0, 'timestamp': '2025-01-01 12:15'},
            {'forecasted_power_kw': 2.0, 'timestamp': '2025-01-01 12:30'},
            {'forecasted_power_kw': 2.0, 'timestamp': '2025-01-01 12:45'}
        ]
        
        energy_needed = 2.0  # kWh
        available = self.analyzer._calculate_pv_availability(pv_forecast, energy_needed)
        
        # 4 forecasts * 2kW * 0.25h = 2kWh
        self.assertEqual(available, 2.0)
    
    def test_get_historical_consumption_for_hour(self):
        """Test historical consumption retrieval for specific hour"""
        # Add historical data for hour 12
        self.analyzer.consumption_history = [
            {'timestamp': datetime.now(), 'consumption_w': 1500, 'hour': 12},
            {'timestamp': datetime.now(), 'consumption_w': 1200, 'hour': 12},
            {'timestamp': datetime.now(), 'consumption_w': 1800, 'hour': 12},
            {'timestamp': datetime.now(), 'consumption_w': 1000, 'hour': 11}  # Different hour
        ]
        
        avg_consumption = self.analyzer._get_historical_consumption_for_hour(12)
        expected_avg = (1500 + 1200 + 1800) / 3  # 1500W
        self.assertEqual(avg_consumption, expected_avg)
    
    def test_calculate_consumption_confidence(self):
        """Test consumption forecast confidence calculation"""
        # Test with no data
        confidence = self.analyzer._calculate_consumption_confidence()
        self.assertEqual(confidence, 0.0)
        
        # Test with limited data
        self.analyzer.consumption_history = [{'timestamp': datetime.now(), 'consumption_w': 1500, 'hour': 12}] * 20
        confidence = self.analyzer._calculate_consumption_confidence()
        self.assertEqual(confidence, 0.5)
        
        # Test with sufficient data
        self.analyzer.consumption_history = [{'timestamp': datetime.now(), 'consumption_w': 1500, 'hour': 12}] * 100
        confidence = self.analyzer._calculate_consumption_confidence()
        self.assertEqual(confidence, 0.9)

class TestPowerBalance(unittest.TestCase):
    """Test cases for PowerBalance dataclass"""
    
    def test_power_balance_creation(self):
        """Test PowerBalance object creation"""
        timestamp = datetime.now()
        power_balance = PowerBalance(
            pv_power_w=2000,
            consumption_power_w=1500,
            net_power_w=500,
            battery_power_w=0,
            grid_power_w=-500,
            timestamp=timestamp,
            confidence=0.9
        )
        
        self.assertEqual(power_balance.pv_power_w, 2000)
        self.assertEqual(power_balance.consumption_power_w, 1500)
        self.assertEqual(power_balance.net_power_w, 500)
        self.assertEqual(power_balance.battery_power_w, 0)
        self.assertEqual(power_balance.grid_power_w, -500)
        self.assertEqual(power_balance.timestamp, timestamp)
        self.assertEqual(power_balance.confidence, 0.9)

class TestChargingRecommendation(unittest.TestCase):
    """Test cases for ChargingRecommendation dataclass"""
    
    def test_charging_recommendation_creation(self):
        """Test ChargingRecommendation object creation"""
        recommendation = ChargingRecommendation(
            should_charge=True,
            charging_source='hybrid',
            priority='critical',
            reason='Low price window - hybrid charging to capture savings',
            estimated_duration_hours=2.0,
            energy_needed_kwh=3.0,
            confidence=0.9,
            pv_available_kwh=1.0,
            grid_needed_kwh=2.0
        )
        
        self.assertTrue(recommendation.should_charge)
        self.assertEqual(recommendation.charging_source, 'hybrid')
        self.assertEqual(recommendation.priority, 'critical')
        self.assertEqual(recommendation.estimated_duration_hours, 2.0)
        self.assertEqual(recommendation.energy_needed_kwh, 3.0)
        self.assertEqual(recommendation.confidence, 0.9)
        self.assertEqual(recommendation.pv_available_kwh, 1.0)
        self.assertEqual(recommendation.grid_needed_kwh, 2.0)

class TestNightChargingStrategy(unittest.TestCase):
    """Test cases for Night Charging Strategy"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'timing_awareness': {
                'battery_capacity_kwh': 10.0,
                'charging_rate_kw': 3.0,
                'pv_capacity_kw': 10.0
            },
            'pv_consumption_analysis': {
                'pv_overproduction_threshold_w': 500,
                'consumption_forecast_hours': 4,
                'historical_data_days': 7,
                'night_charging_enabled': True,
                'night_hours': [22, 23, 0, 1, 2, 3, 4, 5],
                'high_price_threshold_percentile': 0.75,
                'poor_pv_threshold_percentile': 25.0,
                'min_night_charging_soc': 30.0,
                'max_night_charging_soc': 80.0
            },
            'electricity_pricing': {
                'sc_component_pln_kwh': 0.0892
            }
        }
        self.analyzer = PVConsumptionAnalyzer(self.config)
    
    def test_night_charging_strategy_night_hours(self):
        """Test night charging strategy during night hours"""
        # Mock PV forecast with poor production (24 hours of data for better confidence)
        pv_forecast = []
        for hour in range(24):
            pv_forecast.append({
                'forecasted_power_kw': 0.3,  # Poor PV production
                'timestamp': f'2025-01-02 {hour:02d}:00'
            })
        
        # Mock price data with low current price and high tomorrow prices
        price_data = {
            'value': [
                # Current day prices (low)
                {'dtime': '2025-01-01 12:00', 'csdac_pln': '100'},
                {'dtime': '2025-01-01 13:00', 'csdac_pln': '120'},
                {'dtime': '2025-01-01 14:00', 'csdac_pln': '110'},
                {'dtime': '2025-01-01 15:00', 'csdac_pln': '105'},
                {'dtime': '2025-01-01 16:00', 'csdac_pln': '115'},
                {'dtime': '2025-01-01 17:00', 'csdac_pln': '125'},
                {'dtime': '2025-01-01 18:00', 'csdac_pln': '130'},
                {'dtime': '2025-01-01 19:00', 'csdac_pln': '140'},
                {'dtime': '2025-01-01 20:00', 'csdac_pln': '150'},
                {'dtime': '2025-01-01 21:00', 'csdac_pln': '160'},
                {'dtime': '2025-01-01 22:00', 'csdac_pln': '170'},
                {'dtime': '2025-01-01 23:00', 'csdac_pln': '50'},   # Very low current price
                # Tomorrow's prices (high prices)
                {'dtime': '2025-01-02 00:00', 'csdac_pln': '95'},
                {'dtime': '2025-01-02 01:00', 'csdac_pln': '90'},
                {'dtime': '2025-01-02 02:00', 'csdac_pln': '85'},
                {'dtime': '2025-01-02 03:00', 'csdac_pln': '80'},
                {'dtime': '2025-01-02 04:00', 'csdac_pln': '75'},
                {'dtime': '2025-01-02 05:00', 'csdac_pln': '70'},
                {'dtime': '2025-01-02 06:00', 'csdac_pln': '65'},
                {'dtime': '2025-01-02 07:00', 'csdac_pln': '60'},
                {'dtime': '2025-01-02 08:00', 'csdac_pln': '55'},
                {'dtime': '2025-01-02 09:00', 'csdac_pln': '50'},
                {'dtime': '2025-01-02 10:00', 'csdac_pln': '45'},
                {'dtime': '2025-01-02 11:00', 'csdac_pln': '40'},
                {'dtime': '2025-01-02 12:00', 'csdac_pln': '400'},  # High tomorrow price
                {'dtime': '2025-01-02 13:00', 'csdac_pln': '450'},  # High tomorrow price
                {'dtime': '2025-01-02 14:00', 'csdac_pln': '500'},  # High tomorrow price
                {'dtime': '2025-01-02 15:00', 'csdac_pln': '480'},  # High tomorrow price
                {'dtime': '2025-01-02 16:00', 'csdac_pln': '420'},  # High tomorrow price
                {'dtime': '2025-01-02 17:00', 'csdac_pln': '380'},  # High tomorrow price
                {'dtime': '2025-01-02 18:00', 'csdac_pln': '200'},  # Medium tomorrow price
                {'dtime': '2025-01-02 19:00', 'csdac_pln': '150'},  # Low tomorrow price
                {'dtime': '2025-01-02 20:00', 'csdac_pln': '120'},  # Low tomorrow price
                {'dtime': '2025-01-02 21:00', 'csdac_pln': '110'},  # Low tomorrow price
                {'dtime': '2025-01-02 22:00', 'csdac_pln': '105'},  # Low tomorrow price
                {'dtime': '2025-01-02 23:00', 'csdac_pln': '100'}   # Low tomorrow price
            ]
        }
        
        with patch('pv_consumption_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 23, 0)  # Night time
            mock_datetime.strptime = datetime.strptime
            
            recommendation = self.analyzer.analyze_night_charging_strategy(
                20.0, pv_forecast, price_data  # Low battery SOC
            )
            
            self.assertTrue(recommendation.should_charge)
            self.assertEqual(recommendation.charging_source, 'grid')
            self.assertEqual(recommendation.priority, 'critical')
            self.assertIn('Night charging for high price day preparation', recommendation.reason)
    
    def test_night_charging_strategy_daytime(self):
        """Test night charging strategy during daytime hours"""
        pv_forecast = []
        price_data = {'value': []}
        
        with patch('pv_consumption_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0)  # Day time
            mock_datetime.strptime = datetime.strptime
            
            recommendation = self.analyzer.analyze_night_charging_strategy(
                20.0, pv_forecast, price_data
            )
            
            self.assertFalse(recommendation.should_charge)
            self.assertEqual(recommendation.charging_source, 'none')
            self.assertIn('Not in night hours', recommendation.reason)
    
    def test_night_charging_strategy_high_soc(self):
        """Test night charging strategy with high battery SOC"""
        pv_forecast = []
        price_data = {'value': []}
        
        with patch('pv_consumption_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 23, 0)  # Night time
            mock_datetime.strptime = datetime.strptime
            
            recommendation = self.analyzer.analyze_night_charging_strategy(
                50.0, pv_forecast, price_data  # High battery SOC
            )
            
            self.assertFalse(recommendation.should_charge)
            self.assertEqual(recommendation.charging_source, 'none')
            self.assertIn('Battery SOC (50.0%) too high for night charging', recommendation.reason)
    
    def test_battery_discharge_strategy_high_price(self):
        """Test battery discharge strategy during high price period"""
        current_data = {
            'photovoltaic': {'current_power_w': 500},
            'consumption': {'current_power_w': 2000},
            'battery': {'current_power_w': 0},
            'grid': {'current_power_w': 1500}
        }
        
        pv_forecast = []
        price_data = {
            'value': [
                {'dtime': '2025-01-01 12:00', 'csdac_pln': '400'},  # High price
                {'dtime': '2025-01-01 12:15', 'csdac_pln': '420'},  # High price
                {'dtime': '2025-01-01 12:30', 'csdac_pln': '380'},  # High price
                {'dtime': '2025-01-01 12:45', 'csdac_pln': '200'},  # Medium price
                {'dtime': '2025-01-01 13:00', 'csdac_pln': '150'},  # Low price
                {'dtime': '2025-01-01 13:15', 'csdac_pln': '120'},  # Low price
                {'dtime': '2025-01-01 13:30', 'csdac_pln': '100'},  # Low price
                {'dtime': '2025-01-01 13:45', 'csdac_pln': '90'}    # Low price
            ]
        }
        
        with patch('pv_consumption_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0)  # Day time
            mock_datetime.strptime = datetime.strptime
            
            recommendation = self.analyzer.analyze_battery_discharge_strategy(
                60.0, current_data, pv_forecast, price_data  # Good battery SOC
            )
            
            self.assertTrue(recommendation['should_discharge'])
            self.assertIn('High price period', recommendation['reason'])
            self.assertGreater(recommendation['discharge_power_w'], 0)
    
    def test_battery_discharge_strategy_night_time(self):
        """Test battery discharge strategy during night time (should not discharge)"""
        current_data = {
            'photovoltaic': {'current_power_w': 0},
            'consumption': {'current_power_w': 2000},
            'battery': {'current_power_w': 0},
            'grid': {'current_power_w': 2000}
        }
        
        pv_forecast = []
        price_data = {'value': []}
        
        with patch('pv_consumption_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 23, 0)  # Night time
            mock_datetime.strptime = datetime.strptime
            
            recommendation = self.analyzer.analyze_battery_discharge_strategy(
                60.0, current_data, pv_forecast, price_data
            )
            
            self.assertFalse(recommendation['should_discharge'])
            self.assertIn('Night hours - preserving battery charge', recommendation['reason'])
    
    def test_battery_discharge_strategy_low_soc(self):
        """Test battery discharge strategy with low battery SOC"""
        current_data = {
            'photovoltaic': {'current_power_w': 500},
            'consumption': {'current_power_w': 2000},
            'battery': {'current_power_w': 0},
            'grid': {'current_power_w': 1500}
        }
        
        pv_forecast = []
        price_data = {'value': []}
        
        with patch('pv_consumption_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0)  # Day time
            mock_datetime.strptime = datetime.strptime
            
            recommendation = self.analyzer.analyze_battery_discharge_strategy(
                20.0, current_data, pv_forecast, price_data  # Low battery SOC
            )
            
            self.assertFalse(recommendation['should_discharge'])
            self.assertIn('Not in high price period', recommendation['reason'])
    
    def test_is_night_time(self):
        """Test night time detection"""
        # Test night hours
        self.assertTrue(self.analyzer._is_night_time(23))  # 11 PM
        self.assertTrue(self.analyzer._is_night_time(0))   # Midnight
        self.assertTrue(self.analyzer._is_night_time(3))   # 3 AM
        
        # Test day hours
        self.assertFalse(self.analyzer._is_night_time(12))  # Noon
        self.assertFalse(self.analyzer._is_night_time(18))  # 6 PM
        self.assertFalse(self.analyzer._is_night_time(8))   # 8 AM
    
    def test_analyze_tomorrow_pv_forecast(self):
        """Test tomorrow PV forecast analysis"""
        # Test with poor PV forecast
        poor_pv_forecast = [
            {'forecasted_power_kw': 0.5, 'timestamp': '2025-01-02 12:00'},
            {'forecasted_power_kw': 0.3, 'timestamp': '2025-01-02 13:00'},
            {'forecasted_power_kw': 0.2, 'timestamp': '2025-01-02 14:00'}
        ]
        
        analysis = self.analyzer._analyze_tomorrow_pv_forecast(poor_pv_forecast)
        
        # The threshold is 25% of 10kW = 2.5kW, so 0.33kW average should be poor
        self.assertTrue(analysis['is_poor_pv'])
        self.assertLess(analysis['avg_pv_kw'], 2.5)  # Should be below threshold
        self.assertGreater(analysis['confidence'], 0)
        
        # Test with good PV forecast
        good_pv_forecast = [
            {'forecasted_power_kw': 8.0, 'timestamp': '2025-01-02 12:00'},
            {'forecasted_power_kw': 9.0, 'timestamp': '2025-01-02 13:00'},
            {'forecasted_power_kw': 7.5, 'timestamp': '2025-01-02 14:00'}
        ]
        
        analysis = self.analyzer._analyze_tomorrow_pv_forecast(good_pv_forecast)
        
        self.assertFalse(analysis['is_poor_pv'])
        self.assertGreater(analysis['avg_pv_kw'], 5.0)  # Should be high
    
    def test_analyze_tomorrow_price_forecast(self):
        """Test tomorrow price forecast analysis"""
        price_data = {
            'value': [
                # Tomorrow's prices (high prices)
                {'dtime': '2025-01-02 12:00', 'csdac_pln': '400'},
                {'dtime': '2025-01-02 13:00', 'csdac_pln': '450'},
                {'dtime': '2025-01-02 14:00', 'csdac_pln': '500'},
                {'dtime': '2025-01-02 15:00', 'csdac_pln': '480'},
                {'dtime': '2025-01-02 16:00', 'csdac_pln': '420'},
                {'dtime': '2025-01-02 17:00', 'csdac_pln': '380'},
                {'dtime': '2025-01-02 18:00', 'csdac_pln': '200'},
                {'dtime': '2025-01-02 19:00', 'csdac_pln': '150'},
                {'dtime': '2025-01-02 20:00', 'csdac_pln': '120'},
                {'dtime': '2025-01-02 21:00', 'csdac_pln': '110'},
                {'dtime': '2025-01-02 22:00', 'csdac_pln': '105'},
                {'dtime': '2025-01-02 23:00', 'csdac_pln': '100'},
                {'dtime': '2025-01-03 00:00', 'csdac_pln': '95'},
                {'dtime': '2025-01-03 01:00', 'csdac_pln': '90'},
                {'dtime': '2025-01-03 02:00', 'csdac_pln': '85'},
                {'dtime': '2025-01-03 03:00', 'csdac_pln': '80'},
                {'dtime': '2025-01-03 04:00', 'csdac_pln': '75'},
                {'dtime': '2025-01-03 05:00', 'csdac_pln': '70'},
                {'dtime': '2025-01-03 06:00', 'csdac_pln': '65'},
                {'dtime': '2025-01-03 07:00', 'csdac_pln': '60'},
                {'dtime': '2025-01-03 08:00', 'csdac_pln': '55'},
                {'dtime': '2025-01-03 09:00', 'csdac_pln': '50'},
                {'dtime': '2025-01-03 10:00', 'csdac_pln': '45'},
                {'dtime': '2025-01-03 11:00', 'csdac_pln': '40'}
            ]
        }
        
        with patch('pv_consumption_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 23, 0)
            mock_datetime.strptime = datetime.strptime
            
            analysis = self.analyzer._analyze_tomorrow_price_forecast(price_data)
            
            self.assertTrue(analysis['has_high_prices'])
            self.assertGreaterEqual(analysis['high_price_hours'], 4)  # At least 4 high price hours
            self.assertGreater(analysis['confidence'], 0)

if __name__ == '__main__':
    unittest.main()
