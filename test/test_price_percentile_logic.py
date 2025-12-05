"""
Test suite for price percentile logic used in Normal tier (50%+ SOC).

Tests the _is_price_cheap_for_normal_tier() method which implements:
- 40th percentile threshold (always charge if below)
- 60th percentile threshold (charge if below AND SOC < 85%)
- Fallback to cheapest_next_24h × 1.10 when adaptive disabled
- Error handling for missing data
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.automated_price_charging import AutomatedPriceCharger


@pytest.fixture
def config():
    """Standard test configuration."""
    return {
        'automated_price_charging': {
            'enabled': True,
            'emergency_battery_threshold': 5,
            'critical_battery_threshold': 12,
            'smart_critical': {
                'simple_charging': {
                    'flip_flop_protection_minutes': 15,
                    'opportunistic_tolerance_percent': 15
                },
                'adaptive_thresholds': {
                    'enabled': True
                },
                'fallback_critical_price_pln': 0.70
            }
        },
        'data_storage': {
            'database_storage': {
                'enabled': True,
                'db_path': ':memory:'
            }
        },
        'goodwe': {'inverter_ip': '192.168.1.100'},
        'tariff_pricing': {'enabled': False}
    }


@pytest.fixture
def price_charging(config):
    """Create AutomatedPriceCharger instance with mocked dependencies."""
    with patch('src.automated_price_charging.GoodWeFastCharger'):
        with patch('src.automated_price_charging.PriceHistoryManager') as MockPriceHistory:
            # Create a mock price_history instance
            mock_price_history = Mock()
            MockPriceHistory.return_value = mock_price_history
            
            instance = AutomatedPriceCharger(config)
            # Ensure price_history is set (in case initialization doesn't set it)
            if not hasattr(instance, 'price_history') or instance.price_history is None:
                instance.price_history = mock_price_history
            return instance


@pytest.fixture
def sample_price_data():
    """Generate 24 hours of price data with known distribution."""
    now = datetime.now()
    prices = []
    # Create a distribution: 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95 (repeating)
    base_prices = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    
    for hour in range(24):
        prices.append({
            'hour': (now + timedelta(hours=hour)).replace(minute=0, second=0, microsecond=0),
            'price_pln_per_kwh': base_prices[hour % len(base_prices)]
        })
    return prices


@pytest.fixture
def mock_price_history(sample_price_data):
    """Mock PriceHistoryManager with sample data."""
    mock = Mock()
    # Extract just the price values for percentile calculation
    recent_prices = [p['price_pln_per_kwh'] for p in sample_price_data]
    mock.get_recent_prices.return_value = recent_prices
    return mock


# =============================================================================
# PERCENTILE CALCULATION TESTS
# =============================================================================

def test_percentile_below_40th_always_cheap(price_charging, sample_price_data, mock_price_history):
    """Test that prices below 40th percentile are always considered cheap."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    # Calculate expected 40th percentile
    prices = [p['price_pln_per_kwh'] for p in sample_price_data]
    p40 = np.percentile(prices, 40)
    
    # Test price just below p40
    test_price = p40 - 0.01
    result = price_charging._is_price_cheap_for_normal_tier(test_price, 60.0, sample_price_data)
    
    assert result is True


def test_percentile_between_40th_60th_depends_on_soc(price_charging, sample_price_data, mock_price_history):
    """Test prices between 40th-60th percentile depend on SOC < 85%."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    prices = [p['price_pln_per_kwh'] for p in sample_price_data]
    p40 = np.percentile(prices, 40)
    p60 = np.percentile(prices, 60)
    
    # Test price between p40 and p60
    test_price = (p40 + p60) / 2
    
    # Should be cheap when SOC < 85%
    result_low_soc = price_charging._is_price_cheap_for_normal_tier(test_price, 80.0, sample_price_data)
    assert result_low_soc is True
    
    # Should not be cheap when SOC >= 85%
    result_high_soc = price_charging._is_price_cheap_for_normal_tier(test_price, 85.0, sample_price_data)
    assert result_high_soc is False


def test_percentile_above_60th_not_cheap(price_charging, sample_price_data, mock_price_history):
    """Test that prices above 60th percentile are not cheap regardless of SOC."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    prices = [p['price_pln_per_kwh'] for p in sample_price_data]
    p60 = np.percentile(prices, 60)
    
    # Test price above p60
    test_price = p60 + 0.05
    
    # Should not be cheap even at low SOC
    result_low_soc = price_charging._is_price_cheap_for_normal_tier(test_price, 60.0, sample_price_data)
    assert result_low_soc is False
    
    result_high_soc = price_charging._is_price_cheap_for_normal_tier(test_price, 85.0, sample_price_data)
    assert result_high_soc is False


def test_percentile_exact_40th_boundary(price_charging, sample_price_data, mock_price_history):
    """Test boundary case: exactly at 40th percentile."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    prices = [p['price_pln_per_kwh'] for p in sample_price_data]
    p40 = np.percentile(prices, 40)
    
    result = price_charging._is_price_cheap_for_normal_tier(p40, 60.0, sample_price_data)
    assert result is True  # <= 40th percentile


def test_percentile_exact_60th_boundary(price_charging, sample_price_data, mock_price_history):
    """Test boundary case: exactly at 60th percentile."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    prices = [p['price_pln_per_kwh'] for p in sample_price_data]
    p60 = np.percentile(prices, 60)
    
    # At p60 with SOC < 85%
    result_low_soc = price_charging._is_price_cheap_for_normal_tier(p60, 80.0, sample_price_data)
    assert result_low_soc is True  # <= 60th percentile AND SOC < 85%
    
    # At p60 with SOC >= 85%
    result_high_soc = price_charging._is_price_cheap_for_normal_tier(p60, 85.0, sample_price_data)
    assert result_high_soc is False


# =============================================================================
# FALLBACK LOGIC TESTS
# =============================================================================

def test_fallback_when_adaptive_disabled(price_charging, sample_price_data):
    """Test fallback to cheapest_next_24h × 1.10 when adaptive disabled."""
    price_charging.adaptive_enabled = False
    price_charging.price_history = None
    
    with patch.object(price_charging, '_find_cheapest_price_next_hours') as mock_find:
        mock_find.return_value = 0.50
        
        # Within 10% threshold: 0.50 * 1.10 = 0.55
        result_cheap = price_charging._is_price_cheap_for_normal_tier(0.54, 60.0, sample_price_data)
        assert result_cheap is True
        
        # Above threshold
        result_expensive = price_charging._is_price_cheap_for_normal_tier(0.56, 60.0, sample_price_data)
        assert result_expensive is False


def test_fallback_when_no_price_history(price_charging, sample_price_data):
    """Test fallback when price history manager is None."""
    price_charging.adaptive_enabled = True
    price_charging.price_history = None
    
    with patch.object(price_charging, '_find_cheapest_price_next_hours') as mock_find:
        mock_find.return_value = 0.50
        
        result = price_charging._is_price_cheap_for_normal_tier(0.54, 60.0, sample_price_data)
        
        # Should use fallback logic
        assert result is True
        mock_find.assert_called_once_with(24, sample_price_data)


def test_fallback_when_insufficient_price_history(price_charging, sample_price_data, mock_price_history):
    """Test fallback when price history has < 12 hours of data."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    # Return insufficient data (< 12 values)
    mock_price_history.get_recent_prices.return_value = [0.50, 0.55, 0.60, 0.65, 0.70]
    
    with patch.object(price_charging, '_find_cheapest_price_next_hours') as mock_find:
        mock_find.return_value = 0.50
        
        result = price_charging._is_price_cheap_for_normal_tier(0.54, 60.0, sample_price_data)
        
        # Should use fallback
        assert result is True
        mock_find.assert_called_once_with(24, sample_price_data)


# =============================================================================
# ERROR HANDLING & EDGE CASES
# =============================================================================

def test_null_current_price(price_charging, sample_price_data):
    """Test handling of None current_price."""
    result = price_charging._is_price_cheap_for_normal_tier(None, 60.0, sample_price_data)
    assert result is False


def test_empty_price_data(price_charging):
    """Test handling of empty price_data."""
    result = price_charging._is_price_cheap_for_normal_tier(0.50, 60.0, [])
    assert result is False


def test_null_price_data(price_charging):
    """Test handling of None price_data."""
    result = price_charging._is_price_cheap_for_normal_tier(0.50, 60.0, None)
    assert result is False


def test_price_data_with_none_values(price_charging, sample_price_data, mock_price_history):
    """Test handling when price_data contains None values."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    # Add some None values to price data
    dirty_data = sample_price_data.copy()
    dirty_data[5]['price_pln_per_kwh'] = None
    dirty_data[10]['price_pln_per_kwh'] = None
    
    # Should handle gracefully
    result = price_charging._is_price_cheap_for_normal_tier(0.50, 60.0, dirty_data)
    assert isinstance(result, bool)


def test_extreme_price_values(price_charging, sample_price_data, mock_price_history):
    """Test handling of extreme price values."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    # Test very high price
    result_high = price_charging._is_price_cheap_for_normal_tier(999.99, 60.0, sample_price_data)
    assert result_high is False
    
    # Test negative price (can happen in some markets)
    result_negative = price_charging._is_price_cheap_for_normal_tier(-0.10, 60.0, sample_price_data)
    assert result_negative is True  # Negative is definitely cheap


def test_zero_price(price_charging, sample_price_data, mock_price_history):
    """Test handling of zero price."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    result = price_charging._is_price_cheap_for_normal_tier(0.0, 60.0, sample_price_data)
    assert result is True  # Zero is definitely cheap


# =============================================================================
# INTEGRATION WITH _find_cheapest_price_next_hours
# =============================================================================

def test_fallback_calls_find_cheapest_with_24_hours(price_charging, sample_price_data):
    """Test that fallback logic queries 24 hours ahead."""
    price_charging.adaptive_enabled = False
    
    with patch.object(price_charging, '_find_cheapest_price_next_hours') as mock_find:
        mock_find.return_value = 0.50
        
        price_charging._is_price_cheap_for_normal_tier(0.54, 60.0, sample_price_data)
        
        mock_find.assert_called_once_with(24, sample_price_data)


def test_fallback_handles_none_from_find_cheapest(price_charging, sample_price_data):
    """Test fallback when _find_cheapest_price_next_hours returns None."""
    price_charging.adaptive_enabled = False
    
    with patch.object(price_charging, '_find_cheapest_price_next_hours') as mock_find:
        mock_find.return_value = None
        
        result = price_charging._is_price_cheap_for_normal_tier(0.54, 60.0, sample_price_data)
        
        # Should return False when cannot determine
        assert result is False


# =============================================================================
# NUMPY PERCENTILE CALCULATION VERIFICATION
# =============================================================================

def test_percentile_calculation_matches_numpy(price_charging, sample_price_data, mock_price_history):
    """Verify percentile calculation matches numpy.percentile."""
    price_charging.price_history = mock_price_history
    price_charging.adaptive_enabled = True
    
    prices = [p['price_pln_per_kwh'] for p in sample_price_data]
    expected_p40 = np.percentile(prices, 40)
    expected_p60 = np.percentile(prices, 60)
    
    # Mock to return the exact prices
    mock_price_history.get_recent_prices.return_value = prices
    
    # Test around p40
    result_below_p40 = price_charging._is_price_cheap_for_normal_tier(expected_p40 - 0.001, 60.0, sample_price_data)
    assert result_below_p40 is True
    
    result_above_p40 = price_charging._is_price_cheap_for_normal_tier(expected_p40 + 0.001, 80.0, sample_price_data)
    # Between p40 and p60 with SOC < 85% should be cheap
    if expected_p40 + 0.001 <= expected_p60:
        assert result_above_p40 is True
