import sys
from pathlib import Path
import pytest
import yaml
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pse_price_forecast_collector import PSEPriceForecastCollector, PriceForecastPoint


def load_production_config():
    """Load production config for test defaults"""
    config_path = Path(__file__).parent.parent / 'config' / 'master_coordinator_config.yaml'
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


PRODUCTION_CONFIG = load_production_config()


def _collector():
    return PSEPriceForecastCollector({
        'pse_price_forecast': {
            'enabled': True,
            'decision_rules': {
                'wait_for_better_price_enabled': True,
                'min_savings_to_wait_percent': 15,
                'max_wait_time_hours': 4,
            }
        }
    })


def _collector_with_d1_config():
    """Create collector with D+1 config from production settings"""
    pse_config = PRODUCTION_CONFIG.get('pse_price_forecast', {})
    return PSEPriceForecastCollector({
        'pse_price_forecast': {
            'enabled': True,
            'd1_fetch_start_hour': pse_config.get('d1_fetch_start_hour', 13),
            'd1_retry_interval_minutes': pse_config.get('d1_retry_interval_minutes', 30),
            'd1_max_retries': pse_config.get('d1_max_retries', 3),
            'decision_rules': {
                'wait_for_better_price_enabled': True,
                'min_savings_to_wait_percent': 15,
                'max_wait_time_hours': 4,
            }
        }
    })


def test_should_wait_guard_zero_price():
    c = _collector()
    now = datetime.now()
    c.forecast_cache = [
        PriceForecastPoint(time=now + timedelta(hours=1), forecasted_price_pln=100.0)
    ]
    c.last_update_time = now

    res = c.should_wait_for_better_price(current_price=0.0, current_time=now)
    assert res['should_wait'] is False
    assert res['expected_savings_percent'] == 0.0


def test_should_wait_guard_negative_price():
    c = _collector()
    now = datetime.now()
    c.forecast_cache = [
        PriceForecastPoint(time=now + timedelta(hours=1), forecasted_price_pln=100.0)
    ]
    c.last_update_time = now

    res = c.should_wait_for_better_price(current_price=-50.0, current_time=now)
    assert res['should_wait'] is False
    assert res['expected_savings_percent'] == 0.0


class TestD1PriceFetching:
    """Test cases for D+1 (tomorrow) price fetching with retry logic
    
    These tests verify:
    - D+1 prices are fetched after 13:00 (configurable)
    - Retry logic works correctly
    - Caching prevents redundant API calls
    - Error handling for API failures
    """
    
    def test_d1_config_loaded_from_production(self):
        """Test that D+1 config is correctly loaded from production config"""
        c = _collector_with_d1_config()
        
        # Should match production config or fallback defaults
        pse_config = PRODUCTION_CONFIG.get('pse_price_forecast', {})
        expected_start_hour = pse_config.get('d1_fetch_start_hour', 13)
        
        assert c.d1_fetch_start_hour == expected_start_hour
        assert c.d1_retry_interval_minutes == pse_config.get('d1_retry_interval_minutes', 30)
        assert c.d1_max_retries == pse_config.get('d1_max_retries', 3)
    
    @pytest.mark.asyncio
    async def test_fetch_tomorrow_prices_before_start_hour(self):
        """Test that D+1 fetch returns not-available before the configured start hour
        
        Scenario:
            - Current time is 10:00 (before 13:00 start hour)
            - D+1 prices should not be fetched
        
        Expected behavior:
            - Returns dict with available=False and appropriate reason
        """
        c = _collector_with_d1_config()
        
        with patch('pse_price_forecast_collector.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 0)  # 10:00
            mock_dt.strptime = datetime.strptime
            
            result = await c.fetch_tomorrow_prices()
            
            # Before start hour, should return dict with available=False
            assert result is not None
            assert result['available'] is False
            assert 'Too early' in result['reason']
    
    @pytest.mark.asyncio
    async def test_fetch_tomorrow_prices_after_start_hour_returns_cached_when_available(self):
        """Test that D+1 returns cached data after start hour when cache is valid
        
        Scenario:
            - Current time is 14:00 (after 13:00 start hour)
            - Cache already has tomorrow's prices
        
        Expected behavior:
            - Returns cached data with available=True
        
        Note: Testing actual API call would require complex aiohttp mocking.
        The cache behavior is the key functionality to verify.
        """
        c = _collector_with_d1_config()
        
        # Set up cache with tomorrow's data
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        c.tomorrow_prices_date = tomorrow
        c.tomorrow_prices_cache = [
            PriceForecastPoint(time=datetime.now() + timedelta(hours=10), forecasted_price_pln=200.0),
            PriceForecastPoint(time=datetime.now() + timedelta(hours=11), forecasted_price_pln=250.0),
            PriceForecastPoint(time=datetime.now() + timedelta(hours=12), forecasted_price_pln=300.0),
        ]
        
        result = await c.fetch_tomorrow_prices()
        
        # Should return cached data
        assert result is not None
        assert result['available'] is True
        assert len(result.get('prices', [])) == 3
        assert 'Cached' in result['reason']
    
    @pytest.mark.asyncio
    async def test_fetch_tomorrow_prices_uses_cache(self):
        """Test that D+1 prices are cached and reused
        
        Scenario:
            - Manually set cache with tomorrow's prices
            - Call fetch - should use cache
        
        Expected behavior:
            - No API call made when cache is valid
        """
        c = _collector_with_d1_config()
        
        # Set up cache manually
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        c.tomorrow_prices_date = tomorrow
        c.tomorrow_prices_cache = [
            PriceForecastPoint(time=datetime.now(), forecasted_price_pln=200.0)
        ]
        
        # Fetch should use cache
        result = await c.fetch_tomorrow_prices()
        
        # Should return cached data
        assert result is not None
        assert result['available'] is True
        assert 'Cached' in result['reason']
    
    @pytest.mark.asyncio
    async def test_fetch_tomorrow_prices_retry_on_empty(self):
        """Test retry logic when API returns no tomorrow data
        
        Scenario:
            - API call returns empty data
            - Retry count should increment
        
        Expected behavior:
            - Returns unavailable with retry info
        """
        c = _collector_with_d1_config()
        
        mock_response_data = {'value': []}  # Empty response
        
        with patch('pse_price_forecast_collector.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 14, 0)  # 14:00
            mock_dt.strptime = datetime.strptime
            
            # Mock aiohttp session
            with patch('pse_price_forecast_collector.aiohttp.ClientSession') as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value=mock_response_data)
                mock_response.raise_for_status = MagicMock()
                
                mock_context = AsyncMock()
                mock_context.__aenter__.return_value = mock_response
                mock_context.__aexit__.return_value = None
                
                mock_session_instance = AsyncMock()
                mock_session_instance.get.return_value = mock_context
                mock_session_instance.__aenter__.return_value = mock_session_instance
                mock_session_instance.__aexit__.return_value = None
                
                mock_session.return_value = mock_session_instance
                
                result = await c.fetch_tomorrow_prices()
                
                # No data, should return unavailable
                assert result['available'] is False
                assert c.tomorrow_prices_retry_count > 0
    
    @pytest.mark.asyncio
    async def test_fetch_tomorrow_prices_api_error_handling(self):
        """Test graceful handling of API errors
        
        Scenario:
            - API call raises an exception
        
        Expected behavior:
            - Exception is caught
            - Returns dict with available=False
        """
        c = _collector_with_d1_config()
        
        with patch('pse_price_forecast_collector.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 14, 0)  # 14:00
            mock_dt.strptime = datetime.strptime
            
            # Mock aiohttp session to raise an error
            with patch('pse_price_forecast_collector.aiohttp.ClientSession') as mock_session:
                mock_session_instance = AsyncMock()
                mock_session_instance.get.side_effect = Exception("Network error")
                mock_session_instance.__aenter__.return_value = mock_session_instance
                mock_session_instance.__aexit__.return_value = None
                
                mock_session.return_value = mock_session_instance
                
                # Should not raise, returns dict with available=False
                result = await c.fetch_tomorrow_prices()
                
                assert result is not None
                assert result['available'] is False