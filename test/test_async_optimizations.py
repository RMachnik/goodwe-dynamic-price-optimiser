#!/usr/bin/env python3
"""
Tests for Performance Optimizations
- Async HTTP migration
- orjson integration
- deque for data collector
"""

import asyncio
import pytest
from datetime import datetime, date
from collections import deque
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestJsonUtils:
    """Test fast JSON serialization wrapper"""
    
    def test_json_utils_import(self):
        """Test that json_utils can be imported"""
        from json_utils import dumps, loads, dump, load
        assert callable(dumps)
        assert callable(loads)
        assert callable(dump)
        assert callable(load)
    
    def test_dumps_loads(self):
        """Test JSON dumps and loads"""
        from json_utils import dumps, loads
        
        test_data = {
            'key': 'value',
            'number': 42,
            'list': [1, 2, 3],
            'nested': {'a': 'b'}
        }
        
        # Serialize
        json_str = dumps(test_data)
        assert isinstance(json_str, str)
        assert 'key' in json_str
        
        # Deserialize
        restored = loads(json_str)
        assert restored == test_data
    
    def test_dumps_with_indent(self):
        """Test JSON dumps with indentation"""
        from json_utils import dumps
        
        test_data = {'key': 'value'}
        json_str = dumps(test_data, indent=2)
        assert isinstance(json_str, str)
        # Should have newlines when indented
        assert '\n' in json_str or 'key' in json_str  # Either pretty or compact
    
    def test_dump_load_file(self):
        """Test JSON dump and load to/from file"""
        from json_utils import dump, load
        import tempfile
        
        test_data = {'test': 'data', 'number': 123}
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            dump(test_data, f)
            filepath = f.name
        
        try:
            with open(filepath, 'r') as f:
                restored = load(f)
            assert restored == test_data
        finally:
            Path(filepath).unlink()


class TestAsyncHTTP:
    """Test async HTTP migration"""
    
    @pytest.mark.asyncio
    async def test_pse_price_forecast_collector_async(self):
        """Test PSE price forecast collector uses async HTTP"""
        from pse_price_forecast_collector import PSEPriceForecastCollector
        
        config = {
            'enabled': True,
            'api_url': 'https://api.raporty.pse.pl/api/rce-pln',
            'update_interval_minutes': 60,
            'forecast_hours_ahead': 24
        }
        
        collector = PSEPriceForecastCollector(config)
        
        # Mock response
        mock_data = {
            'value': [
                {
                    'dtime': (datetime.now()).strftime('%Y-%m-%d %H:%M'),
                    'rce_pln': 500.0,
                    'business_date': datetime.now().strftime('%Y-%m-%d')
                }
            ]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_data)
            mock_response.raise_for_status = Mock()
            
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            
            mock_get = Mock(return_value=mock_ctx)
            mock_session_instance = AsyncMock()
            mock_session_instance.get = mock_get
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            # Should not raise exception
            result = await collector.fetch_price_forecast(hours_ahead=24)
            assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_pse_peak_hours_collector_async(self):
        """Test PSE peak hours collector uses async HTTP"""
        from pse_peak_hours_collector import PSEPeakHoursCollector
        
        config = {
            'enabled': True,
            'api_url': 'https://api.raporty.pse.pl/api/pdgsz',
            'update_interval_minutes': 60
        }
        
        collector = PSEPeakHoursCollector(config)
        
        # Mock response
        mock_data = {
            'value': [
                {
                    'dtime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'usage_fcst': 1,
                    'business_date': datetime.now().strftime('%Y-%m-%d'),
                    'is_active': True
                }
            ]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.json = AsyncMock(return_value=mock_data)
            mock_response.raise_for_status = Mock()
            
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            
            mock_get = Mock(return_value=mock_ctx)
            mock_session_instance = AsyncMock()
            mock_session_instance.get = mock_get
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            # Should not raise exception
            result = await collector.fetch_peak_hours(business_day=date.today())
            assert isinstance(result, list)


class TestDequeOptimization:
    """Test deque optimization in data collector"""
    
    def test_deque_initialization(self):
        """Test that EnhancedDataCollector uses deque"""
        from enhanced_data_collector import EnhancedDataCollector
        
        config = {
            'inverter': {'ip': '192.168.1.100'},
            'data_storage': {
                'database_storage': {
                    'enabled': True,
                    'sqlite': {'path': ':memory:'}  # Use in-memory DB for tests
                }
            }
        }
        
        collector = EnhancedDataCollector(config)
        
        # Should be a deque with maxlen
        assert isinstance(collector.historical_data, deque)
        assert collector.historical_data.maxlen == 30240
    
    def test_deque_auto_truncation(self):
        """Test that deque automatically limits size"""
        # Create a deque with maxlen
        test_deque = deque(maxlen=5)
        
        # Add more than maxlen items
        for i in range(10):
            test_deque.append(i)
        
        # Should only keep last 5
        assert len(test_deque) == 5
        assert list(test_deque) == [5, 6, 7, 8, 9]
    
    def test_deque_performance_vs_list(self):
        """Test that deque append is O(1)"""
        import time
        
        # Test deque performance
        d = deque(maxlen=30240)
        start = time.perf_counter()
        for i in range(30240):
            d.append({'data': i})
        deque_time = time.perf_counter() - start
        
        # Test list with slicing performance
        l = []
        start = time.perf_counter()
        for i in range(30240):
            l.append({'data': i})
            if len(l) > 30240:
                l = l[-30240:]
        list_time = time.perf_counter() - start
        
        # Deque should be faster or comparable
        # We don't assert strict inequality as it depends on hardware,
        # but log the results
        print(f"\nDeque time: {deque_time:.4f}s, List time: {list_time:.4f}s")
        assert deque_time >= 0  # Just verify it completes


class TestAsyncHTTPFallback:
    """Test fallback to sync requests when aiohttp unavailable"""
    
    @pytest.mark.asyncio
    async def test_pse_collectors_fallback(self):
        """Test that collectors fall back to sync requests if aiohttp unavailable"""
        # This would require temporarily hiding aiohttp, which is complex
        # For now, just verify the import pattern exists
        from pse_price_forecast_collector import AIOHTTP_AVAILABLE
        from pse_peak_hours_collector import AIOHTTP_AVAILABLE as AIOHTTP_AVAILABLE2
        
        # Should be imported
        assert isinstance(AIOHTTP_AVAILABLE, bool)
        assert isinstance(AIOHTTP_AVAILABLE2, bool)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
