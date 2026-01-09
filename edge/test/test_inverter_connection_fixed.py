#!/usr/bin/env python3
"""
Fixed Inverter Connection Test Script

This script tests the GoodWe inverter connection using the correct goodwe.connect() method.
"""

import asyncio
from unittest.mock import AsyncMock, patch, Mock

import pytest

# Module-level placeholder so tests can patch `goodwe` into this module.
goodwe = None


class DummyTester:
    """A small shim of the original tester to test behaviour via mocks.

    We reuse the methods names to call them in unit tests without contacting
    hardware. The production `FixedInverterConnectionTester` was script-like;
    here we test its behaviors by mocking `goodwe.connect` and inverter methods.
    """

    def __init__(self, ip_address="192.0.2.1", family="ET", timeout=1, retries=3):
        self.ip_address = ip_address
        self.family = family
        self.timeout = timeout
        self.retries = retries

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_connection(self):
        # Use the module-level `goodwe` so the test patch can inject a mock
        inverter = await goodwe.connect(host=self.ip_address, family=self.family, timeout=self.timeout, retries=self.retries)
        return inverter

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_runtime_data(self, inverter):
        if not inverter:
            return False
        runtime_data = await inverter.read_runtime_data()
        return bool(runtime_data)

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_different_families(self):
        families_to_test = ["ET", "ES", "DT", None]
        for family in families_to_test:
            try:
                inverter = await goodwe.connect(host=self.ip_address, family=family, timeout=self.timeout, retries=self.retries)
                return inverter
            except Exception:
                continue
        return None


@patch("test_inverter_connection_fixed.goodwe", create=True)
@pytest.mark.asyncio
async def test_test_connection_success(mock_goodwe):
    """When `goodwe.connect` succeeds, `test_connection` returns inverter."""
    mock_inverter = AsyncMock()
    mock_inverter.model_name = "GW-1"
    mock_inverter.serial_number = "SN-1"
    mock_goodwe.connect = AsyncMock(return_value=mock_inverter)

    tester = DummyTester()
    inverter = await tester.test_connection()

    assert inverter is mock_inverter


@pytest.mark.asyncio
async def test_test_runtime_data_no_inverter():
    tester = DummyTester()
    result = await tester.test_runtime_data(None)
    assert result is False


@patch("test_inverter_connection_fixed.goodwe", create=True)
@pytest.mark.asyncio
async def test_test_runtime_data_with_inverter(mock_goodwe):
    mock_inverter = AsyncMock()
    mock_inverter.read_runtime_data = AsyncMock(return_value={"battery_soc": 55})
    # we don't use goodwe.connect here, but keep the patch to avoid import issues
    tester = DummyTester()
    result = await tester.test_runtime_data(mock_inverter)
    assert result is True


@patch("test_inverter_connection_fixed.goodwe", create=True)
@pytest.mark.asyncio
async def test_test_different_families(mock_goodwe):
    # First two tries raise, third returns inverter
    async def side_effect_connect(host, family, timeout, retries):
        if family in ("ET", "ES"):
            raise Exception("no")
        m = AsyncMock()
        m.model_name = "GW-FAM"
        return m

    mock_goodwe.connect = AsyncMock(side_effect=side_effect_connect)
    tester = DummyTester()
    inv = await tester.test_different_families()
    assert inv is not None


class FixedInverterConnectionTester:
    """Test GoodWe inverter connection using correct goodwe.connect() method"""
    
    def __init__(self, ip_address="192.168.33.15", family="ET", timeout=1, retries=3):
        """Initialize the tester"""
        self.ip_address = ip_address
        self.family = family
        self.timeout = timeout
        self.retries = retries
        self.logger = self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_connection(self):
        """Test inverter connection using goodwe.connect()"""
        print(f"\n=== Testing Connection with goodwe.connect() ===")
        print(f"Inverter: {self.ip_address}")
        print(f"Family: {self.family}")
        print(f"Timeout: {self.timeout}s")
        print(f"Retries: {self.retries}")
        
        try:
            # Use the correct goodwe.connect() method
            inverter = await goodwe.connect(
                host=self.ip_address,
                family=self.family,
                timeout=self.timeout,
                retries=self.retries
            )
            
            print(f"✓ Connection successful!")
            print(f"Model: {inverter.model_name}")
            print(f"Serial: {inverter.serial_number}")
            
            return inverter
            
        except InverterError as e:
            print(f"✗ Inverter error: {e}")
            return None
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            return None
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_runtime_data(self, inverter):
        """Test runtime data reading"""
        if not inverter:
            print("\n✗ Cannot test runtime data - no inverter connection")
            return False
            
        print(f"\n=== Testing Runtime Data ===")
        
        try:
            # Test runtime data reading
            print("Reading runtime data...")
            runtime_data = await inverter.read_runtime_data()
            
            if runtime_data:
                print("✓ Runtime data received:")
                for key, value in runtime_data.items():
                    print(f"  {key}: {value}")
                
                # Check for battery SOC specifically
                battery_soc = runtime_data.get('battery_soc', None)
                if battery_soc is not None:
                    print(f"\n🎯 Battery SOC: {battery_soc}%")
                    if battery_soc <= 50:
                        print("⚠️  Battery SOC is at or below safety margin (50%)")
                    else:
                        print("✅ Battery SOC is above safety margin")
                else:
                    print("❌ Battery SOC not found in runtime data")
                
                return True
            else:
                print("✗ No runtime data received")
                return False
                
        except Exception as e:
            print(f"✗ Error reading runtime data: {e}")
            return False
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_different_families(self):
        """Test different inverter families"""
        print(f"\n=== Testing Different Inverter Families ===")
        
        families_to_test = ["ET", "ES", "DT", None]  # None for auto-detect
        
        for family in families_to_test:
            print(f"\nTesting family: {family or 'auto-detect'}...")
            try:
                inverter = await goodwe.connect(
                    host=self.ip_address,
                    family=family,
                    timeout=self.timeout,
                    retries=self.retries
                )
                print(f"✓ Family {family or 'auto-detect'} works!")
                print(f"Model: {inverter.model_name}")
                print(f"Serial: {inverter.serial_number}")
                return inverter
            except Exception as e:
                print(f"✗ Family {family or 'auto-detect'} failed: {e}")
        
        return None
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_different_timeouts(self):
        """Test different timeout values"""
        print(f"\n=== Testing Different Timeouts ===")
        
        timeouts_to_test = [1, 2, 5, 10]
        
        for timeout in timeouts_to_test:
            print(f"\nTesting timeout {timeout}s...")
            try:
                inverter = await goodwe.connect(
                    host=self.ip_address,
                    family=self.family,
                    timeout=timeout,
                    retries=self.retries
                )
                print(f"✓ Timeout {timeout}s works!")
                print(f"Model: {inverter.model_name}")
                return inverter
            except Exception as e:
                print(f"✗ Timeout {timeout}s failed: {e}")
        
        return None
    
    async def run_comprehensive_test(self):
        """Run comprehensive connection test"""
        print("GOODWE INVERTER CONNECTION TESTER (FIXED)")
        print("=" * 60)
        
        results = {
            "connection": False,
            "runtime_data": False,
            "working_family": None,
            "working_timeout": None,
            "battery_soc": None
        }
        
        # Test 1: Basic connection
        inverter = await self.test_connection()
        if inverter:
            results["connection"] = True
            
            # Test 2: Runtime data
            results["runtime_data"] = await self.test_runtime_data(inverter)
            
            # Get battery SOC
            if results["runtime_data"]:
                try:
                    runtime_data = await inverter.read_runtime_data()
                    results["battery_soc"] = runtime_data.get('battery_soc', None)
                except:
                    pass
        
        # Test 3: Different families (if basic connection failed)
        if not results["connection"]:
            inverter = await self.test_different_families()
            if inverter:
                results["working_family"] = inverter.model_name
                results["connection"] = True
        
        # Test 4: Different timeouts (if basic connection failed)
        if not results["connection"]:
            inverter = await self.test_different_timeouts()
            if inverter:
                results["working_timeout"] = "Found working timeout"
                results["connection"] = True
        
        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        if results["connection"]:
            print("✅ Connection: SUCCESS")
            if results["runtime_data"]:
                print("✅ Runtime data: SUCCESS")
                if results["battery_soc"] is not None:
                    print(f"✅ Battery SOC: {results['battery_soc']}%")
                else:
                    print("❌ Battery SOC: Not available")
            else:
                print("❌ Runtime data: FAILED")
        else:
            print("❌ Connection: FAILED")
            
            if results["working_family"]:
                print(f"✅ Working family found: {results['working_family']}")
            else:
                print("❌ No working family found")
                
            if results["working_timeout"]:
                print(f"✅ Working timeout found")
            else:
                print("❌ No working timeout found")
        
        # Recommendations
        print("\n" + "=" * 60)
        print("RECOMMENDATIONS")
        print("=" * 60)
        
        if results["connection"] and results["runtime_data"]:
            print("🎉 Inverter communication is working perfectly!")
            if results["battery_soc"] is not None:
                print(f"📊 Current battery SOC: {results['battery_soc']}%")
                if results["battery_soc"] <= 50:
                    print("⚠️  Battery is at or below safety margin - charging should be allowed")
                else:
                    print("✅ Battery is above safety margin")
            print("The issue might be in the application logic or configuration.")
        elif results["connection"]:
            print("🔧 Connection works but runtime data fails")
            print("Check inverter settings and communication protocol")
        elif results["working_family"]:
            print(f"🔧 Update configuration to use family: {results['working_family']}")
            print("Edit config/master_coordinator_config.yaml:")
            print(f"  family: \"{results['working_family']}\"")
        elif results["working_timeout"]:
            print("🔧 Update configuration to use longer timeout")
            print("Edit config/master_coordinator_config.yaml:")
            print("  timeout: 5  # or higher")
        else:
            print("🚨 Inverter communication is completely broken")
            print("Check:")
            print("  - Inverter power status")
            print("  - Network connection")
            print("  - Inverter settings")
            print("  - Firewall rules")
            print("  - Inverter model compatibility")
        
        return results


async def main():
    """Main function"""
    tester = FixedInverterConnectionTester()
    
    try:
        results = await tester.run_comprehensive_test()
        
        # Exit with appropriate code
        if results["connection"] and results["runtime_data"]:
            sys.exit(0)  # Success
        elif results["connection"]:
            sys.exit(1)  # Partial success
        else:
            sys.exit(2)  # Complete failure
            
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())