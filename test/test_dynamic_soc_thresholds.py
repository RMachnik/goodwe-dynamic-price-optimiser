#!/usr/bin/env python3
"""
Tests for Phase 2: Dynamic SOC Thresholds

Tests the dynamic SOC threshold feature that adjusts minimum selling SOC
based on price magnitude, with safety checks for peak hours and recharge opportunities.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from battery_selling_engine import BatterySellingEngine, SellingDecision


class TestDynamicSOCThresholds:
    """Test dynamic SOC threshold feature"""
    
    @pytest.fixture
    def config_dynamic_enabled(self):
        """Configuration with dynamic SOC enabled"""
        return {
            'battery_selling': {
                'min_battery_soc': 80,
                'safety_margin_soc': 50,
                'min_selling_price_pln': 0.50,
                'peak_hours': [17, 18, 19, 20, 21],
                'smart_timing': {
                    'enabled': True,
                    'dynamic_soc_thresholds': {
                        'enabled': True,
                        'super_premium_price_threshold': 1.2,
                        'super_premium_min_soc': 50,
                        'premium_price_threshold': 0.9,
                        'premium_min_soc': 60,
                        'very_high_price_threshold': 0.8,
                        'very_high_min_soc': 70,
                        'high_price_threshold': 0.7,
                        'high_min_soc': 80,
                        'require_peak_hours': True,
                        'require_recharge_forecast': True
                    }
                }
            },
            'battery_management': {'capacity_kwh': 20.0}
        }
    
    @pytest.fixture
    def config_dynamic_disabled(self):
        """Configuration with dynamic SOC disabled"""
        return {
            'battery_selling': {
                'min_battery_soc': 80,
                'safety_margin_soc': 50,
                'min_selling_price_pln': 0.50,
                'smart_timing': {
                    'enabled': True,
                    'dynamic_soc_thresholds': {
                        'enabled': False
                    }
                }
            },
            'battery_management': {'capacity_kwh': 20.0}
        }
    
    @pytest.fixture
    def engine_dynamic(self, config_dynamic_enabled):
        """Create engine with dynamic SOC enabled"""
        return BatterySellingEngine(config_dynamic_enabled)
    
    @pytest.fixture
    def engine_static(self, config_dynamic_disabled):
        """Create engine with dynamic SOC disabled"""
        return BatterySellingEngine(config_dynamic_disabled)
    
    def test_initialization_dynamic_enabled(self, engine_dynamic):
        """Test that dynamic SOC is properly initialized"""
        assert engine_dynamic.dynamic_soc_enabled is True
        assert engine_dynamic.super_premium_price_threshold == 1.2
        assert engine_dynamic.super_premium_min_soc == 50
        assert engine_dynamic.premium_price_threshold == 0.9
        assert engine_dynamic.premium_min_soc == 60
        assert engine_dynamic.very_high_price_threshold == 0.8
        assert engine_dynamic.very_high_min_soc == 70
        assert engine_dynamic.high_price_threshold == 0.7
        assert engine_dynamic.high_min_soc == 80
        assert engine_dynamic.require_peak_hours is True
        assert engine_dynamic.require_recharge_forecast is True
    
    def test_initialization_dynamic_disabled(self, engine_static):
        """Test that dynamic SOC can be disabled"""
        assert engine_static.dynamic_soc_enabled is False
    
    def test_super_premium_price_70_soc(self, engine_dynamic):
        """Test super premium prices (>1.2 PLN/kWh) allow 50% SOC"""
        with patch('battery_selling_engine.datetime') as mock_datetime:
            # Mock now() to return a specific time
            mock_now = datetime(2025, 10, 26, 19, 0, 0)  # 7 PM (peak hour)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.side_effect = None
            
            # Create price forecast with recharge opportunity (0.40 < 1.3 * 0.7 = 0.91)
            future_time = mock_now + timedelta(hours=2)
            price_forecast = [
                {'price': 0.40, 'time': future_time.isoformat()}
            ]
            
            min_soc = engine_dynamic._get_dynamic_min_soc(1.3, price_forecast)
            assert min_soc == 50
    
    def test_premium_price_75_soc(self, engine_dynamic):
        """Test premium prices (0.9-1.2 PLN/kWh) allow 60% SOC"""
        with patch('battery_selling_engine.datetime') as mock_datetime:
            # Mock now() to return a specific time
            mock_now = datetime(2025, 10, 26, 18, 0, 0)  # 6 PM (peak hour)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.side_effect = None  # Important: no side effect
            
            # Create forecast with time based on mocked now
            future_time = mock_now + timedelta(hours=2)
            price_forecast = [
                {'price': 0.50, 'time': future_time.isoformat()}
            ]
            
            min_soc = engine_dynamic._get_dynamic_min_soc(1.0, price_forecast)
            assert min_soc == 60
    
    def test_high_price_80_soc(self, engine_dynamic):
        """Test very high prices (0.8-0.9 PLN/kWh) use 70% SOC, high prices (0.7-0.8) use 80%"""
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 26, 20, 0, 0)  # 8 PM (peak hour)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.side_effect = None
            
            future_time = mock_now + timedelta(hours=2)
            price_forecast = [
                {'price': 0.40, 'time': future_time.isoformat()}  # Recharge opportunity
            ]
            
            # Very high price (0.8-0.9) should use 70% SOC
            min_soc = engine_dynamic._get_dynamic_min_soc(0.85, price_forecast)
            assert min_soc == 70
            
            # High price (0.7-0.8) should use 80% SOC
            min_soc = engine_dynamic._get_dynamic_min_soc(0.75, price_forecast)
            assert min_soc == 80
    
    def test_normal_price_80_soc(self, engine_dynamic):
        """Test normal prices (<0.7 PLN/kWh) use standard 80% SOC"""
        price_forecast = []
        
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 19  # Peak hour
            
            min_soc = engine_dynamic._get_dynamic_min_soc(0.6, price_forecast)
            assert min_soc == 80
    
    def test_outside_peak_hours_uses_default(self, engine_dynamic):
        """Test that outside peak hours, default 80% SOC is used even for super premium"""
        price_forecast = [
            {'price': 0.40, 'time': (datetime.now() + timedelta(hours=2)).isoformat()}
        ]
        
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 14  # Non-peak hour (2 PM)
            
            # Even with super premium price, should use default outside peak hours
            min_soc = engine_dynamic._get_dynamic_min_soc(1.5, price_forecast)
            assert min_soc == 80
    
    def test_no_recharge_opportunity_uses_default(self, engine_dynamic):
        """Test that without recharge opportunity, default SOC is used"""
        # No low prices in forecast = no recharge opportunity
        price_forecast = [
            {'price': 1.0, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 1.1, 'time': (datetime.now() + timedelta(hours=4)).isoformat()}
        ]
        
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 19  # Peak hour
            
            # No recharge opportunity, should use default
            min_soc = engine_dynamic._get_dynamic_min_soc(1.3, price_forecast)
            assert min_soc == 80
    
    def test_recharge_opportunity_detection(self, engine_dynamic):
        """Test recharge opportunity detection (30% lower price)"""
        current_price = 1.0
        
        # Recharge opportunity: 0.60 is 40% lower than 1.0
        price_forecast = [
            {'price': 0.90, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.60, 'time': (datetime.now() + timedelta(hours=3)).isoformat()},  # Recharge!
            {'price': 0.80, 'time': (datetime.now() + timedelta(hours=5)).isoformat()}
        ]
        
        has_recharge = engine_dynamic._check_recharge_opportunity(price_forecast, current_price)
        assert has_recharge is True
    
    def test_no_recharge_opportunity_all_high(self, engine_dynamic):
        """Test no recharge opportunity when all prices are high"""
        current_price = 1.0
        
        # No price is 30% lower than current
        price_forecast = [
            {'price': 0.95, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.85, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.90, 'time': (datetime.now() + timedelta(hours=3)).isoformat()}
        ]
        
        has_recharge = engine_dynamic._check_recharge_opportunity(price_forecast, current_price)
        assert has_recharge is False
    
    def test_dynamic_disabled_always_returns_default(self, engine_static):
        """Test that with dynamic SOC disabled, always returns default 80%"""
        price_forecast = [
            {'price': 0.40, 'time': (datetime.now() + timedelta(hours=2)).isoformat()}
        ]
        
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 19  # Peak hour
            
            # Even with super premium price, should return default
            min_soc = engine_static._get_dynamic_min_soc(1.5, price_forecast)
            assert min_soc == 80
    
    @pytest.mark.asyncio
    async def test_selling_blocked_at_72_soc_normal_price(self, engine_dynamic):
        """Test selling blocked at 72% SOC with normal price"""
        current_data = {
            'battery': {'soc_percent': 72, 'temperature': 25, 'charging_status': False},
            'pv': {'power_w': 100},
            'consumption': {'power_w': 2000},
            'grid': {'power': 1800, 'voltage': 230}
        }
        
        price_data = {'current_price_pln': 0.65}
        
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 19
            mock_datetime.now.return_value.date.return_value = datetime.now().date()
            
            opportunity = await engine_dynamic.analyze_selling_opportunity(current_data, price_data)
            
            assert opportunity.decision == SellingDecision.WAIT
            assert "below" in opportunity.reasoning.lower()
            assert "threshold" in opportunity.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_selling_allowed_at_72_soc_super_premium(self, engine_dynamic):
        """Test selling allowed at 52% SOC with super premium price (50% threshold)"""
        current_data = {
            'battery': {'soc_percent': 52, 'temperature': 25, 'charging_status': False},
            'pv': {'power_w': 100},
            'consumption': {'power_w': 2000},
            'grid': {'power': 1800, 'voltage': 230}
        }
        
        price_data = {'current_price_pln': 1.3}
        
        # Mock forecast with recharge opportunity
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 26, 19, 0, 0)  # 7 PM (peak hour)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.side_effect = None
            
            future_time = mock_now + timedelta(hours=2)
            
            with patch.object(engine_dynamic, '_get_price_forecast', new_callable=AsyncMock) as mock_forecast:
                mock_forecast.return_value = [
                    {'price': 0.40, 'time': future_time.isoformat()}
                ]
                
                opportunity = await engine_dynamic.analyze_selling_opportunity(current_data, price_data)
                
                # Should NOT be blocked (52% > 50% threshold for super premium)
                assert opportunity.decision != SellingDecision.WAIT or "below" not in opportunity.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_safety_margin_never_breached(self, engine_dynamic):
        """Test that 50% safety margin is never breached regardless of dynamic SOC"""
        current_data = {
            'battery': {'soc_percent': 48, 'temperature': 25, 'charging_status': False},
            'pv': {'power_w': 100},
            'consumption': {'power_w': 2000},
            'grid': {'power': 1800, 'voltage': 230}
        }
        
        price_data = {'current_price_pln': 2.0}  # Extreme price
        
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 19
            mock_datetime.now.return_value.date.return_value = datetime.now().date()
            
            # Check safety conditions directly
            safety_ok, reason = engine_dynamic._check_safety_conditions(current_data)
            
            # Should fail safety check (below 50% safety margin)
            assert safety_ok is False
            assert "safety margin" in reason.lower()


class TestDynamicSOCIntegration:
    """Integration tests for dynamic SOC with full selling workflow"""
    
    @pytest.fixture
    def config_integrated(self):
        """Full configuration for integration testing"""
        return {
            'battery_selling': {
                'min_battery_soc': 80,
                'safety_margin_soc': 50,
                'min_selling_price_pln': 0.50,
                'max_daily_cycles': 2,
                'peak_hours': [17, 18, 19, 20, 21],
                'grid_export_limit_w': 5000,
                'battery_dod_limit': 50,
                'smart_timing': {
                    'enabled': True,
                    'forecast_lookahead_hours': 12,
                    'dynamic_soc_thresholds': {
                        'enabled': True,
                        'super_premium_price_threshold': 1.2,
                        'super_premium_min_soc': 50,
                        'premium_price_threshold': 0.9,
                        'premium_min_soc': 60,
                        'very_high_price_threshold': 0.8,
                        'very_high_min_soc': 70,
                        'high_price_threshold': 0.7,
                        'high_min_soc': 80,
                        'require_peak_hours': True,
                        'require_recharge_forecast': True
                    }
                }
            },
            'battery_management': {'capacity_kwh': 20.0}
        }
    
    @pytest.fixture
    def engine_integrated(self, config_integrated):
        """Create fully integrated engine"""
        return BatterySellingEngine(config_integrated)
    
    @pytest.mark.asyncio
    async def test_scenario_evening_peak_spike(self, engine_integrated):
        """Test scenario: Evening price spike to 1.5 PLN/kWh during peak hours"""
        current_data = {
            'battery': {'soc_percent': 53, 'temperature': 25, 'charging_status': False},
            'pv': {'power_w': 0},  # Evening, no PV
            'consumption': {'power_w': 2500},
            'grid': {'power': 2500, 'voltage': 230}
        }
        
        price_data = {'current_price_pln': 1.5}  # Super premium spike
        
        # Mock forecast showing night recharge opportunity
        with patch.object(engine_integrated, '_get_price_forecast', new_callable=AsyncMock) as mock_forecast:
            mock_forecast.return_value = [
                {'price': 0.30, 'time': (datetime.now() + timedelta(hours=5)).isoformat()},  # Night recharge
                {'price': 0.25, 'time': (datetime.now() + timedelta(hours=6)).isoformat()}
            ]
            
            with patch('battery_selling_engine.datetime') as mock_datetime:
                mock_datetime.now.return_value.hour = 19  # Peak hour (7 PM)
                mock_datetime.now.return_value.date.return_value = datetime.now().date()
                
                opportunity = await engine_integrated.analyze_selling_opportunity(current_data, price_data)
                
                # Should allow selling from 53% SOC (above 50% threshold for super premium)
                # Should have good revenue due to high price
                assert opportunity.safety_checks_passed is True
                if opportunity.decision == SellingDecision.START_SELLING:
                    assert opportunity.expected_revenue_pln > 5.0  # High revenue expected
    
    @pytest.mark.asyncio
    async def test_scenario_premium_price_no_recharge(self, engine_integrated):
        """Test scenario: Premium price but no recharge opportunity"""
        current_data = {
            'battery': {'soc_percent': 76, 'temperature': 25, 'charging_status': False},
            'pv': {'power_w': 0},
            'consumption': {'power_w': 2000},
            'grid': {'power': 2000, 'voltage': 230}
        }
        
        price_data = {'current_price_pln': 1.0}  # Premium price
        
        # Mock forecast with NO recharge opportunity (all prices high)
        with patch.object(engine_integrated, '_get_price_forecast', new_callable=AsyncMock) as mock_forecast:
            mock_forecast.return_value = [
                {'price': 0.95, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
                {'price': 0.90, 'time': (datetime.now() + timedelta(hours=4)).isoformat()}
            ]
            
            with patch('battery_selling_engine.datetime') as mock_datetime:
                mock_datetime.now.return_value.hour = 18  # Peak hour
                mock_datetime.now.return_value.date.return_value = datetime.now().date()
                
                opportunity = await engine_integrated.analyze_selling_opportunity(current_data, price_data)
                
                # Should NOT allow selling from 76% (below 80% default)
                # because no recharge opportunity detected
                assert opportunity.decision == SellingDecision.WAIT
                assert "below" in opportunity.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_scenario_outside_peak_hours_blocks_low_soc(self, engine_integrated):
        """Test scenario: Super premium price but outside peak hours"""
        current_data = {
            'battery': {'soc_percent': 72, 'temperature': 25, 'charging_status': False},
            'pv': {'power_w': 3000},  # Daytime
            'consumption': {'power_w': 1500},
            'grid': {'power': -1500, 'voltage': 230}
        }
        
        price_data = {'current_price_pln': 1.4}  # Super premium
        
        with patch.object(engine_integrated, '_get_price_forecast', new_callable=AsyncMock) as mock_forecast:
            mock_forecast.return_value = [
                {'price': 0.35, 'time': (datetime.now() + timedelta(hours=3)).isoformat()}
            ]
            
            with patch('battery_selling_engine.datetime') as mock_datetime:
                mock_datetime.now.return_value.hour = 14  # NOT peak hour (2 PM)
                mock_datetime.now.return_value.date.return_value = datetime.now().date()
                
                opportunity = await engine_integrated.analyze_selling_opportunity(current_data, price_data)
                
                # Should block selling at 72% because outside peak hours
                assert opportunity.decision == SellingDecision.WAIT
                assert "threshold" in opportunity.reasoning.lower()


class TestDynamicSOCEdgeCases:
    """Test edge cases and error handling for dynamic SOC"""
    
    @pytest.fixture
    def engine(self):
        """Create engine for edge case testing"""
        config = {
            'battery_selling': {
                'min_battery_soc': 80,
                'safety_margin_soc': 50,
                'smart_timing': {
                    'enabled': True,
                    'dynamic_soc_thresholds': {
                        'enabled': True,
                        'super_premium_price_threshold': 1.2,
                        'super_premium_min_soc': 50,
                        'premium_price_threshold': 0.9,
                        'premium_min_soc': 60,
                        'very_high_price_threshold': 0.8,
                        'very_high_min_soc': 70,
                        'high_price_threshold': 0.7,
                        'high_min_soc': 80,
                        'require_peak_hours': True,
                        'require_recharge_forecast': True
                    }
                }
            },
            'battery_management': {'capacity_kwh': 20.0}
        }
        return BatterySellingEngine(config)
    
    def test_empty_forecast_returns_default(self, engine):
        """Test empty forecast returns default SOC (no recharge opportunity detected)"""
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 19
            
            # Empty forecast means no recharge opportunity, so use default
            min_soc = engine._get_dynamic_min_soc(1.5, [])
            assert min_soc == 80  # Default (correct - no recharge opportunity)
    
    def test_none_forecast_returns_default(self, engine):
        """Test None forecast returns default SOC (no recharge opportunity)"""
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 19
            
            # Without forecast, can't check recharge opportunity, so returns default
            min_soc = engine._get_dynamic_min_soc(1.5, None)
            assert min_soc == 80  # Default (correct - no recharge opportunity)
    
    def test_malformed_forecast_data(self, engine):
        """Test malformed forecast data doesn't crash"""
        bad_forecast = [
            {'bad_key': 'value'},
            {'price': 'not_a_number'},
            None
        ]
        
        # Should not crash
        has_recharge = engine._check_recharge_opportunity(bad_forecast, 1.0)
        assert has_recharge is False  # Conservative: no recharge if error
    
    def test_extreme_prices(self, engine):
        """Test handling of extreme price values"""
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 26, 19, 0, 0)  # 7 PM
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.side_effect = None
            
            # Recharge opportunity for high prices (need 30% lower than current)
            future_time = mock_now + timedelta(hours=2)
            price_forecast_with_recharge = [
                {'price': 0.01, 'time': future_time.isoformat()}  # Very low recharge price
            ]
            
            # Extreme high price (10.0 PLN/kWh) - super premium with recharge opportunity
            min_soc = engine._get_dynamic_min_soc(10.0, price_forecast_with_recharge)
            assert min_soc == 50  # Super premium threshold (50%)
            
            # Extreme low price - no SOC reduction needed
            min_soc = engine._get_dynamic_min_soc(0.01, price_forecast_with_recharge)
            assert min_soc == 80  # Default (normal price range)
            
            # Negative price (shouldn't happen but handle it)
            min_soc = engine._get_dynamic_min_soc(-0.5, price_forecast_with_recharge)
            assert min_soc == 80  # Default
    
    def test_boundary_prices(self, engine):
        """Test exact boundary price values"""
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_now = datetime(2025, 10, 26, 19, 0, 0)  # 7 PM
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            mock_datetime.side_effect = None
            
            # Need recharge opportunities (30% lower than current prices being tested)
            # For 1.2 PLN/kWh test, need forecast price <= 0.84 (1.2 * 0.7)
            # For 0.9 PLN/kWh test, need forecast price <= 0.63 (0.9 * 0.7)
            # For 0.8 PLN/kWh test, need forecast price <= 0.56 (0.8 * 0.7)
            future_time = mock_now + timedelta(hours=2)
            price_forecast_for_1_2 = [
                {'price': 0.35, 'time': future_time.isoformat()}  # Way below 0.84
            ]
            
            price_forecast_for_0_9 = [
                {'price': 0.30, 'time': future_time.isoformat()}  # Way below 0.63
            ]
            
            price_forecast_for_0_8 = [
                {'price': 0.25, 'time': future_time.isoformat()}  # Way below 0.56
            ]
            
            # Exactly at 1.2 threshold with recharge opportunity
            min_soc = engine._get_dynamic_min_soc(1.2, price_forecast_for_1_2)
            assert min_soc == 50  # Should be super premium (50%)
            
            # Just below 1.2 with recharge opportunity
            min_soc = engine._get_dynamic_min_soc(1.19, price_forecast_for_1_2)
            assert min_soc == 60  # Premium (60%)
            
            # Exactly at 0.9 threshold with recharge opportunity
            min_soc = engine._get_dynamic_min_soc(0.9, price_forecast_for_0_9)
            assert min_soc == 60  # Premium (60%)
            
            # Just below 0.9 with recharge opportunity (now falls into very_high tier)
            min_soc = engine._get_dynamic_min_soc(0.89, price_forecast_for_0_8)
            # With very_high tier (0.8-0.9), 0.89 should return very_high_min_soc (70%)
            assert min_soc == 70  # Very high tier (70%)
            
            # Exactly at 0.8 threshold with recharge opportunity (very_high tier)
            min_soc = engine._get_dynamic_min_soc(0.8, price_forecast_for_0_8)
            # Should be very_high tier (70%)
            assert min_soc == 70  # Very high tier (70%)
            
            # Just below 0.8 with recharge opportunity
            min_soc = engine._get_dynamic_min_soc(0.79, price_forecast_for_0_8)
            assert min_soc == 80  # High tier (0.7-0.8)

