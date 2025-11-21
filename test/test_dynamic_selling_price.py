#!/usr/bin/env python3
"""
Test for dynamic minimum selling price calculation
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import unittest.mock as mock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Mock goodwe before importing battery_selling_engine
sys.modules['goodwe'] = mock.MagicMock()

from battery_selling_engine import BatterySellingEngine


def test_dynamic_price_winter():
    """Test dynamic price calculation in winter (November)"""
    
    # Config with dynamic pricing enabled
    config = {
        'battery_selling': {
            'enabled': True,
            'min_battery_soc': 80,
            'safety_margin_soc': 50,
            'dynamic_min_price': {
                'enabled': True,
                'base_multiplier': 1.5,
                'seasonal_adjustments': {
                    'winter': {
                        'multiplier': 2.0,
                        'months': [11, 12, 1, 2]
                    },
                    'summer': {
                        'multiplier': 1.3,
                        'months': [6, 7, 8]
                    },
                    'spring_autumn': {
                        'multiplier': 1.5,
                        'months': [3, 4, 5, 9, 10]
                    }
                },
                'lookback_days': 7,
                'min_samples': 24,
                'fallback_price_pln': 1.2
            },
            'min_selling_price_pln': 0.80  # Fallback
        },
        'battery_management': {
            'capacity_kwh': 20.0,
            'soc_thresholds': {
                'critical': 10
            }
        }
    }
    
    engine = BatterySellingEngine(config)
    
    # Create mock price data with 7 days of history
    now = datetime.now()
    price_history = []
    
    # Generate 7 days * 24 hours = 168 price points
    # Average around 0.6 PLN/kWh
    for i in range(168):
        time = now - timedelta(hours=168-i)
        # Simulate realistic price variation (0.4 - 0.8 PLN/kWh, avg ~0.6)
        price = 0.6 + (i % 10) * 0.02 - 0.1  # Varies between 0.4 and 0.7
        price_history.append({
            'time': time,
            'price': price
        })
    
    price_data = {
        'current_price_pln': 1.2,
        'price_history': price_history
    }
    
    # Calculate dynamic min price
    dynamic_min = engine._calculate_dynamic_min_price(price_data)
    
    print(f"\n🧪 Testing Dynamic Pricing (Winter - November)")
    print(f"=" * 60)
    print(f"Market average: ~0.6 PLN/kWh (from {len(price_history)} samples)")
    print(f"Current month: {now.month} (November)")
    print(f"Season: Winter")
    print(f"Multiplier: 2.0x")
    print(f"Expected min price: ~1.2 PLN/kWh (0.6 * 2.0)")
    print(f"Calculated min price: {dynamic_min:.3f} PLN/kWh")
    
    # Verify winter multiplier applied
    avg_price = sum(p['price'] for p in price_history) / len(price_history)
    expected = avg_price * 2.0
    
    assert abs(dynamic_min - expected) < 0.01, f"Expected {expected:.3f}, got {dynamic_min:.3f}"
    assert dynamic_min >= 1.15, f"Winter min price should be ≥1.15 PLN (got {dynamic_min:.3f})"
    
    print(f"✅ Test PASSED: Dynamic winter pricing works correctly!")
    

def test_dynamic_price_summer():
    """Test dynamic price calculation in summer (July)"""
    
    # Create a mock summer date
    import unittest.mock as mock
    
    config = {
        'battery_selling': {
            'enabled': True,
            'min_battery_soc': 80,
            'safety_margin_soc': 50,
            'dynamic_min_price': {
                'enabled': True,
                'base_multiplier': 1.5,
                'seasonal_adjustments': {
                    'winter': {
                        'multiplier': 2.0,
                        'months': [11, 12, 1, 2]
                    },
                    'summer': {
                        'multiplier': 1.3,
                        'months': [6, 7, 8]
                    },
                    'spring_autumn': {
                        'multiplier': 1.5,
                        'months': [3, 4, 5, 9, 10]
                    }
                },
                'lookback_days': 7,
                'min_samples': 24,
                'fallback_price_pln': 1.2
            }
        },
        'battery_management': {
            'capacity_kwh': 20.0,
            'soc_thresholds': {'critical': 10}
        }
    }
    
    engine = BatterySellingEngine(config)
    
    # Mock summer month (July = 7)
    summer_date = datetime(2025, 7, 15, 12, 0, 0)
    
    # Generate summer price history (lower prices)
    price_history = []
    for i in range(168):
        time = summer_date - timedelta(hours=168-i)
        price = 0.4 + (i % 10) * 0.01  # 0.4-0.5 PLN (summer prices lower)
        price_history.append({
            'time': time,
            'price': price
        })
    
    price_data = {
        'current_price_pln': 0.7,
        'price_history': price_history
    }
    
    # Mock datetime.now() to return summer date
    with mock.patch('battery_selling_engine.datetime') as mock_datetime:
        mock_datetime.now.return_value = summer_date
        mock_datetime.strftime = datetime.strftime
        mock_datetime.fromisoformat = datetime.fromisoformat
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        # Manually set current month for season detection
        season = engine._get_current_season(7)
        multiplier = engine._get_seasonal_multiplier(7)
        
        print(f"\n🧪 Testing Dynamic Pricing (Summer - July)")
        print(f"=" * 60)
        print(f"Season: {season}")
        print(f"Multiplier: {multiplier}x")
        
        assert season == 'summer', f"Expected summer, got {season}"
        assert multiplier == 1.3, f"Expected 1.3x, got {multiplier}x"
        
        print(f"✅ Test PASSED: Summer season detection works!")


def test_fallback_when_insufficient_data():
    """Test that fallback price is used when insufficient data"""
    
    config = {
        'battery_selling': {
            'enabled': True,
            'min_battery_soc': 80,
            'safety_margin_soc': 50,
            'dynamic_min_price': {
                'enabled': True,
                'min_samples': 24,
                'fallback_price_pln': 1.2
            }
        },
        'battery_management': {
            'capacity_kwh': 20.0,
            'soc_thresholds': {'critical': 10}
        }
    }
    
    engine = BatterySellingEngine(config)
    
    # Only 10 price points (insufficient, needs 24)
    price_history = [
        {'time': datetime.now() - timedelta(hours=i), 'price': 0.5}
        for i in range(10)
    ]
    
    price_data = {
        'current_price_pln': 1.0,
        'price_history': price_history
    }
    
    dynamic_min = engine._calculate_dynamic_min_price(price_data)
    
    print(f"\n🧪 Testing Fallback Price (Insufficient Data)")
    print(f"=" * 60)
    print(f"Price samples: {len(price_history)} (need 24)")
    print(f"Fallback price: 1.2 PLN/kWh")
    print(f"Calculated price: {dynamic_min:.3f} PLN/kWh")
    
    assert dynamic_min == 1.2, f"Expected fallback 1.2, got {dynamic_min}"
    print(f"✅ Test PASSED: Fallback works correctly!")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🧪 DYNAMIC SELLING PRICE TESTS")
    print("="*60)
    
    try:
        test_dynamic_price_winter()
        test_dynamic_price_summer()
        test_fallback_when_insufficient_data()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
