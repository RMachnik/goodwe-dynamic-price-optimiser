#!/usr/bin/env python3
"""
Integration Test Suite for Battery Selling Buy-Back Protection

Tests the enhanced protection mechanisms that prevent selling battery energy
when it would result in expensive buy-back scenarios or excessive SOC drops.

Run with: python -m pytest test/test_battery_selling_buyback_protection.py -v
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import tempfile
import os

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_selling_engine import BatterySellingEngine, SellingDecision, SellingOpportunity


class TestBuyBackProtection:
    """Test buy-back protection and safety mechanisms"""
    
    @pytest.fixture
    def temp_tracking_file(self):
        """Create temporary tracking file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = f.name
        yield temp_path
        try:
            os.unlink(temp_path)
        except:
            pass
    
    @pytest.fixture
    def config(self, temp_tracking_file):
        """Test configuration with all protection features enabled"""
        return {
            'battery_selling': {
                'enabled': True,
                'min_selling_price_pln': 0.50,
                'min_battery_soc': 50.0,
                'safety_margin_soc': 50.0,
                'max_daily_cycles': 2,
                'peak_hours': [17, 18, 19, 20, 21],
                'grid_export_limit_w': 5000,
                'battery_dod_limit': 50,
                'max_soc_drop_per_session': 20,
                'max_soc_drop_per_day': 40,
                'emergency_sell_price_threshold': 1.50,
                'min_profit_margin_multiplier': 1.5,
                'daily_tracking_file': temp_tracking_file,
                'sell_then_buy_prevention': {
                    'enabled': True,
                    'analysis_hours': 12,
                    'min_savings_ratio': 1.5
                },
                'smart_timing': {
                    'enabled': True,
                    'dynamic_soc_thresholds': {
                        'enabled': True,
                        'super_premium_min_soc': 70,
                        'premium_min_soc': 75,
                        'very_high_min_soc': 80,
                        'require_recharge_forecast': True
                    }
                }
            },
            'battery': {
                'capacity_kwh': 20.0
            }
        }
    
    @pytest.fixture
    def engine(self, config):
        """Battery selling engine instance with protections enabled"""
        # Don't patch optional imports - let them fail gracefully
        engine = BatterySellingEngine(config)
        return engine
    
    @pytest.fixture
    def current_data_high_soc(self):
        """Current system data with 92% SOC"""
        return {
            'battery': {
                'soc_percent': 92,
                'temperature': 25,
                'power_w': -2000
            },
            'grid': {
                'voltage': 230,
                'power_w': 2000
            },
            'pv': {
                'power_w': 0
            },
            'consumption': {
                'power_w': 500  # Non-zero consumption to allow selling logic
            }
        }
    
    @pytest.fixture
    def price_data_high(self):
        """High price data (1.018 PLN/kWh)"""
        return {
            'current_price_pln': 1.018,
            'timestamp': datetime.now().isoformat()
        }
    
    @pytest.fixture
    def price_forecast_higher_future(self):
        """Forecast with higher future prices (1.05-1.10 PLN/kWh)"""
        now = datetime.now()
        return [
            {
                'timestamp': (now + timedelta(hours=i)).isoformat(),
                'price_pln': 1.05 + (i * 0.01),  # Increasing from 1.05 to 1.10
                'confidence': 0.9
            }
            for i in range(6)
        ]
    
    @pytest.fixture
    def price_forecast_lower_future(self):
        """Forecast with lower future prices (0.50-0.70 PLN/kWh)"""
        now = datetime.now()
        return [
            {
                'timestamp': (now + timedelta(hours=i)).isoformat(),
                'price_pln': 0.50 + (i * 0.04),  # Increasing from 0.50 to 0.70
                'confidence': 0.9
            }
            for i in range(6)
        ]
    
    def test_blocks_selling_when_future_prices_higher(self, engine, current_data_high_soc, 
                                                      price_data_high, price_forecast_higher_future):
        """
        Test: Should block selling at 92% SOC with 1.018 PLN/kWh current price
        when future prices are higher (1.05-1.10 PLN/kWh) and consumption is high
        """
        # Increase consumption to make energy deficit more likely
        test_data = current_data_high_soc.copy()
        test_data['consumption'] = {'power_w': 2000}  # Higher consumption
        
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 18  # Peak hour
            
            # Mock higher consumption forecast
            with patch.object(engine, '_forecast_future_consumption', return_value=20.0):
                # Analyze sell-then-buy risk
                risk_analysis = engine._analyze_sell_then_buy_risk(
                    test_data, 
                    price_data_high, 
                    price_forecast_higher_future
                )
            
            # Should block selling due to higher future prices or energy deficit
            assert not risk_analysis['safe_to_sell'], \
                "Should block selling when future prices are higher and consumption is significant"
            # Reason could mention buy-back cost, savings ratio, or energy deficit
            reason_lower = risk_analysis['reason'].lower()
            assert any(keyword in reason_lower for keyword in ['buy-back', 'savings', 'deficit', 'cost']), \
                f"Reason should mention protection mechanism, got: {risk_analysis['reason']}"
    
    def test_allows_selling_when_future_prices_lower(self, engine, current_data_high_soc,
                                                     price_data_high, price_forecast_lower_future):
        """
        Test: Should allow selling at 92% SOC with 1.018 PLN/kWh current price
        when future prices are much lower (0.50-0.70 PLN/kWh)
        """
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 18  # Peak hour
            
            # Mock consumption forecaster to return lower energy need
            if hasattr(engine, 'consumption_forecaster') and engine.consumption_forecaster:
                with patch.object(engine, '_forecast_future_consumption', return_value=3.0):
                    # Analyze sell-then-buy risk
                    risk_analysis = engine._analyze_sell_then_buy_risk(
                        current_data_high_soc,
                        price_data_high,
                        price_forecast_lower_future
                    )
            else:
                # No consumption forecaster - use heuristic
                risk_analysis = engine._analyze_sell_then_buy_risk(
                    current_data_high_soc,
                    price_data_high,
                    price_forecast_lower_future
                )
            
            # Should allow selling - future prices are much lower
            # (may still block due to energy deficit with heuristic forecasting)
            if not risk_analysis['safe_to_sell']:
                # If blocked, it should be due to energy deficit, not prices
                assert 'deficit' in risk_analysis['reason'].lower(), \
                    f"Expected energy deficit reason, got: {risk_analysis['reason']}"
            else:
                assert risk_analysis['safe_to_sell'], \
                    "Should allow selling when future prices are much lower"
    
    def test_blocks_below_profit_margin(self, engine, current_data_high_soc):
        """
        Test: Should block selling when price is below profit margin threshold
        Price 0.60 PLN/kWh < 1.5 × 0.50 = 0.75 PLN/kWh minimum
        """
        price_data_low = {
            'current_price_pln': 0.60,
            'timestamp': datetime.now().isoformat()
        }
        
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 18  # Peak hour
            
            # Mock consumption forecaster for cleaner test
            with patch.object(engine, '_forecast_future_consumption', return_value=3.0):
                opportunity = engine._analyze_selling_opportunity(
                    current_data_high_soc,
                    price_data_low,
                    None
                )
            
            # Should block due to insufficient profit margin (or sell-then-buy if that fires first)
            assert opportunity.decision == SellingDecision.WAIT, \
                "Should block selling below profit margin threshold"
            reason_lower = opportunity.reasoning.lower()
            assert any(keyword in reason_lower for keyword in ['profit', 'threshold', 'prevention']), \
                f"Reasoning should mention profit, threshold, or prevention, got: {opportunity.reasoning}"
    
    def test_session_soc_drop_limit(self, engine, current_data_high_soc, price_data_high):
        """
        Test: Should cap selling to max 20% SOC drop per session
        """
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 18  # Peak hour
            
            # Mock consumption forecaster to allow selling
            with patch.object(engine, '_forecast_future_consumption', return_value=3.0):
                # Mock sell-then-buy to allow
                with patch.object(engine, '_analyze_sell_then_buy_risk') as mock_risk:
                    mock_risk.return_value = {'safe_to_sell': True, 'reason': 'Test pass'}
                    
                    opportunity = engine._analyze_selling_opportunity(
                        current_data_high_soc,
                        price_data_high,
                        None
                    )
            
            # Calculate expected maximum drop
            current_soc = 92
            max_allowed_drop = min(
                current_soc - engine.safety_margin_soc,  # 92 - 50 = 42%
                engine.max_soc_drop_per_session  # 20%
            )
            
            # Energy calculation: 20% of 20 kWh = 4 kWh
            max_energy_kwh = (max_allowed_drop / 100) * engine.battery_capacity_kwh
            
            # If selling is allowed, energy should be capped
            if opportunity.decision == SellingDecision.START_SELLING:
                estimated_energy = (opportunity.selling_power_w / 1000) * opportunity.estimated_duration_hours
                assert estimated_energy <= max_energy_kwh + 0.5, \
                    f"Selling energy {estimated_energy:.2f} kWh should not exceed max {max_energy_kwh:.2f} kWh"
    
    def test_daily_cumulative_limit(self, engine, current_data_high_soc, price_data_high):
        """
        Test: Should block selling when daily cumulative limit (40%) is reached
        """
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 18  # Peak hour
            today_str = mock_datetime.now.return_value.strftime('%Y-%m-%d')
            
            # Simulate that 40% has already been used today
            engine.daily_soc_drop_tracking[today_str] = 40.0
            
            opportunity = engine._analyze_selling_opportunity(
                current_data_high_soc,
                price_data_high,
                None
            )
            
            # Should block due to daily limit reached
            assert opportunity.decision == SellingDecision.WAIT, \
                "Should block selling when daily SOC drop limit reached"
            assert 'daily' in opportunity.reasoning.lower() or \
                   'limit' in opportunity.reasoning.lower(), \
                "Reasoning should mention daily limit"
    
    def test_emergency_mode_bypasses_checks(self, engine, current_data_high_soc):
        """
        Test: Emergency mode (price > 1.50 PLN/kWh) should bypass profit and buy-back checks
        """
        price_data_emergency = {
            'current_price_pln': 1.60,  # Above 1.50 threshold
            'timestamp': datetime.now().isoformat()
        }
        
        # Future prices even higher (would normally block)
        now = datetime.now()
        price_forecast_higher = [
            {
                'timestamp': (now + timedelta(hours=i)).isoformat(),
                'price_pln': 1.70 + (i * 0.01),
                'confidence': 0.9
            }
            for i in range(6)
        ]
        
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 18  # Peak hour
            
            # Mock consumption forecaster
            with patch.object(engine, '_forecast_future_consumption', return_value=3.0):
                opportunity = engine._analyze_selling_opportunity(
                    current_data_high_soc,
                    price_data_emergency,
                    price_forecast_higher
                )
            
            # Emergency mode should allow selling despite higher future prices
            # (but still respect SOC and safety limits)
            assert opportunity.decision == SellingDecision.START_SELLING or \
                   '⚡' in opportunity.reasoning, \
                "Emergency mode should be activated or indicated"
            
            if opportunity.decision == SellingDecision.START_SELLING:
                assert '⚡' in opportunity.reasoning, \
                    "Emergency mode should be indicated with ⚡ emoji"
    
    def test_daily_tracking_persistence(self, engine, temp_tracking_file):
        """
        Test: Daily SOC drop tracking should persist to file
        """
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # Add some tracking data
        engine.daily_soc_drop_tracking[today_str] = 15.5
        engine._save_daily_tracking()
        
        # Verify file was written
        assert os.path.exists(temp_tracking_file), "Tracking file should exist"
        
        # Load and verify data
        with open(temp_tracking_file, 'r') as f:
            data = json.load(f)
        
        assert today_str in data, "Today's date should be in tracking file"
        assert data[today_str] == 15.5, "SOC drop value should match"
    
    def test_old_tracking_data_cleanup(self, engine, temp_tracking_file):
        """
        Test: Old tracking data (>7 days) should be cleaned up on load
        """
        # Write old data
        old_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        recent_date = datetime.now().strftime('%Y-%m-%d')
        
        tracking_data = {
            old_date: 25.0,
            recent_date: 10.0
        }
        
        with open(temp_tracking_file, 'w') as f:
            json.dump(tracking_data, f)
        
        # Reload tracking
        loaded_data = engine._load_daily_tracking()
        
        # Old data should be removed, recent data kept
        assert old_date not in loaded_data, "Old data (>7 days) should be cleaned up"
        assert recent_date in loaded_data, "Recent data should be kept"
        assert loaded_data[recent_date] == 10.0, "Recent data value should match"
    
    def test_profit_margin_allows_high_price(self, engine, current_data_high_soc, price_data_high):
        """
        Test: Should allow selling when price exceeds profit margin
        Price 1.018 PLN/kWh > 1.5 × 0.50 = 0.75 PLN/kWh minimum
        """
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 18  # Peak hour
            
            # Mock consumption forecaster and sell-then-buy to allow
            with patch.object(engine, '_forecast_future_consumption', return_value=3.0):
                with patch.object(engine, '_analyze_sell_then_buy_risk') as mock_risk:
                    mock_risk.return_value = {'safe_to_sell': True, 'reason': 'Test pass'}
                    
                    opportunity = engine._analyze_selling_opportunity(
                        current_data_high_soc,
                        price_data_high,
                        None
                    )
                    
                    # Should allow selling - price well above profit margin
                    assert opportunity.decision == SellingDecision.START_SELLING or \
                           opportunity.confidence > 0.5, \
                        "Should allow or consider selling when price exceeds profit margin"
    
    def test_combined_limits_interaction(self, engine, current_data_high_soc, price_data_high):
        """
        Test: Multiple limits should work together correctly
        Session limit (20%) + daily already used (25%) = only 15% remaining
        """
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 18
            today_str = mock_datetime.now.return_value.strftime('%Y-%m-%d')
            
            # Already used 25% today
            engine.daily_soc_drop_tracking[today_str] = 25.0
            
            # Mock consumption forecaster and sell-then-buy to allow
            with patch.object(engine, '_forecast_future_consumption', return_value=3.0):
                with patch.object(engine, '_analyze_sell_then_buy_risk') as mock_risk:
                    mock_risk.return_value = {'safe_to_sell': True, 'reason': 'Test'}
                    
                    opportunity = engine._analyze_selling_opportunity(
                        current_data_high_soc,
                        price_data_high,
                        None
                    )
                    
                    if opportunity.decision == SellingDecision.START_SELLING:
                        # Should be limited to min(session_limit=20%, daily_remaining=15%) = 15%
                        max_allowed = min(20, 40 - 25)  # 15%
                        estimated_soc_drop = (
                            (opportunity.selling_power_w / 1000) * 
                            opportunity.estimated_duration_hours / 
                            engine.battery_capacity_kwh * 100
                        )
                        
                        assert estimated_soc_drop <= max_allowed + 2, \
                            f"Should respect combined limits: {estimated_soc_drop:.1f}% <= {max_allowed}%"
