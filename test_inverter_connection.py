#!/usr/bin/env python3
"""
Test Inverter Connection Script

This script tests the GoodWe inverter connection and diagnoses communication issues.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import goodwe
    from goodwe import Inverter, InverterError
except ImportError as e:
    print(f"Error importing goodwe library: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


class InverterConnectionTester:
    """Test GoodWe inverter connection and communication"""
    
    def __init__(self, ip_address="192.168.33.15", port=8899, timeout=1):
        """Initialize the tester"""
        self.ip_address = ip_address
        self.port = port
        self.timeout = timeout
        self.logger = self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    async def test_basic_connection(self):
        """Test basic inverter connection"""
        print(f"\n=== Testing Basic Connection ===")
        print(f"Inverter: {self.ip_address}:{self.port}")
        print(f"Timeout: {self.timeout}s")
        
        try:
            # Create inverter instance
            inverter = Inverter(self.ip_address, self.port, self.timeout)
            
            # Test device info reading
            print("Testing device info reading...")
            device_info = await inverter.read_device_info()
            print(f"✓ Device info: {device_info}")
            return True
            
        except InverterError as e:
            print(f"✗ Inverter error: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            return False
    
    async def test_runtime_data(self):
        """Test runtime data reading"""
        print(f"\n=== Testing Runtime Data ===")
        
        try:
            inverter = Inverter(self.ip_address, self.port, self.timeout)
            
            # Test runtime data reading
            print("Testing runtime data reading...")
            runtime_data = await inverter.read_runtime_data()
            
            if runtime_data:
                print("✓ Runtime data received:")
                for key, value in runtime_data.items():
                    print(f"  {key}: {value}")
                return True
            else:
                print("✗ No runtime data received")
                return False
                
        except InverterError as e:
            print(f"✗ Inverter error: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            return False
    
    async def test_different_ports(self):
        """Test different ports to find the correct one"""
        print(f"\n=== Testing Different Ports ===")
        
        ports_to_test = [8899, 8898, 8897, 8896, 8895, 80, 443]
        
        for port in ports_to_test:
            print(f"\nTesting port {port}...")
            try:
                inverter = Inverter(self.ip_address, port, self.timeout)
                device_info = await inverter.read_device_info()
                print(f"✓ Port {port} works! Device: {device_info}")
                return port
            except Exception as e:
                print(f"✗ Port {port} failed: {e}")
        
        return None
    
    async def test_different_timeouts(self):
        """Test different timeout values"""
        print(f"\n=== Testing Different Timeouts ===")
        
        timeouts_to_test = [1, 2, 5, 10]
        
        for timeout in timeouts_to_test:
            print(f"\nTesting timeout {timeout}s...")
            try:
                inverter = Inverter(self.ip_address, self.port, timeout)
                device_info = await inverter.read_device_info()
                print(f"✓ Timeout {timeout}s works! Device: {device_info}")
                return timeout
            except Exception as e:
                print(f"✗ Timeout {timeout}s failed: {e}")
        
        return None
    
    async def test_connection_retry(self):
        """Test connection with retry logic"""
        print(f"\n=== Testing Connection Retry ===")
        
        max_retries = 3
        for attempt in range(max_retries):
            print(f"\nAttempt {attempt + 1}/{max_retries}...")
            try:
                inverter = Inverter(self.ip_address, self.port, self.timeout)
                device_info = await inverter.read_device_info()
                print(f"✓ Connection successful on attempt {attempt + 1}")
                print(f"Device: {device_info}")
                return True
            except Exception as e:
                print(f"✗ Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    print("Waiting 2 seconds before retry...")
                    await asyncio.sleep(2)
        
        return False
    
    async def run_comprehensive_test(self):
        """Run comprehensive connection test"""
        print("GOODWE INVERTER CONNECTION TESTER")
        print("=" * 50)
        
        results = {
            "basic_connection": False,
            "runtime_data": False,
            "working_port": None,
            "working_timeout": None,
            "retry_success": False
        }
        
        # Test 1: Basic connection
        results["basic_connection"] = await self.test_basic_connection()
        
        # Test 2: Runtime data
        if results["basic_connection"]:
            results["runtime_data"] = await self.test_runtime_data()
        
        # Test 3: Different ports
        if not results["basic_connection"]:
            results["working_port"] = await self.test_different_ports()
        
        # Test 4: Different timeouts
        if not results["basic_connection"]:
            results["working_timeout"] = await self.test_different_timeouts()
        
        # Test 5: Retry logic
        if not results["basic_connection"]:
            results["retry_success"] = await self.test_connection_retry()
        
        # Summary
        print("\n" + "=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)
        
        if results["basic_connection"]:
            print("✅ Basic connection: SUCCESS")
            if results["runtime_data"]:
                print("✅ Runtime data: SUCCESS")
            else:
                print("❌ Runtime data: FAILED")
        else:
            print("❌ Basic connection: FAILED")
            
            if results["working_port"]:
                print(f"✅ Working port found: {results['working_port']}")
            else:
                print("❌ No working port found")
                
            if results["working_timeout"]:
                print(f"✅ Working timeout found: {results['working_timeout']}s")
            else:
                print("❌ No working timeout found")
                
            if results["retry_success"]:
                print("✅ Retry logic: SUCCESS")
            else:
                print("❌ Retry logic: FAILED")
        
        # Recommendations
        print("\n" + "=" * 50)
        print("RECOMMENDATIONS")
        print("=" * 50)
        
        if results["basic_connection"] and results["runtime_data"]:
            print("🎉 Inverter communication is working perfectly!")
            print("The issue might be in the application logic.")
        elif results["working_port"]:
            print(f"🔧 Update configuration to use port {results['working_port']}")
            print("Edit config/master_coordinator_config.yaml:")
            print(f"  port: {results['working_port']}")
        elif results["working_timeout"]:
            print(f"🔧 Update configuration to use timeout {results['working_timeout']}s")
            print("Edit config/master_coordinator_config.yaml:")
            print(f"  timeout: {results['working_timeout']}")
        else:
            print("🚨 Inverter communication is completely broken")
            print("Check:")
            print("  - Inverter power status")
            print("  - Network connection")
            print("  - Inverter settings")
            print("  - Firewall rules")
        
        return results


async def main():
    """Main function"""
    tester = InverterConnectionTester()
    
    try:
        results = await tester.run_comprehensive_test()
        
        # Exit with appropriate code
        if results["basic_connection"] and results["runtime_data"]:
            sys.exit(0)  # Success
        elif results["working_port"] or results["working_timeout"]:
            sys.exit(1)  # Partial success
        else:
            sys.exit(2)  # Complete failure
            
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())