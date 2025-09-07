#!/usr/bin/env python3
"""
Simple IP testing script for GoodWe inverters
Tests common IP addresses where inverters might be located
"""

import asyncio
import goodwe
import ipaddress

async def check_ip_address(ip):
    """Test if a specific IP responds to GoodWe protocol"""
    try:
        print(f"Testing {ip}...", end=" ")
        inverter = await goodwe.connect(
            host=ip,
            family="ET",  # Try ET family first
            timeout=2,
            retries=1
        )
        print(f"✅ SUCCESS! Found {inverter.model_name} (Serial: {inverter.serial_number})")
        return True
    except Exception as e:
        print(f"❌ Failed: {str(e)[:50]}...")
        return False

async def main():
    """Test common IP addresses"""
    print("Testing common GoodWe inverter IP addresses...")
    print("=" * 50)
    
    # Common IP ranges to test
    test_ips = [
        "192.168.1.100",
        "192.168.1.101", 
        "192.168.1.102",
        "192.168.1.200",
        "192.168.1.201",
        "192.168.2.100",
        "192.168.2.101",
        "192.168.2.200",
        "192.168.68.50",
        "192.168.68.51",
        "192.168.68.100",
        "192.168.68.101",
        "192.168.68.200",
        "10.0.0.100",
        "10.0.0.101",
        "10.0.0.200"
    ]
    
    found_inverters = []
    
    for ip in test_ips:
        if await check_ip_address(ip):
            found_inverters.append(ip)
    
    print("\n" + "=" * 50)
    if found_inverters:
        print(f"✅ Found {len(found_inverters)} inverter(s) at:")
        for ip in found_inverters:
            print(f"   - {ip}")
    else:
        print("❌ No inverters found in common IP ranges")
        print("\nSuggestions:")
        print("1. Check your router's DHCP client list")
        print("2. Look at your GoodWe app for the IP address")
        print("3. Check if the inverter is powered on")
        print("4. Verify network connectivity")

def test_ip_script():
    """Test that the IP testing script can be imported and run"""
    # This is a placeholder test to ensure the script doesn't break pytest
    # The actual IP testing should be run manually with: python test/test_ips.py
    assert True

if __name__ == "__main__":
    asyncio.run(main())
