#!/usr/bin/env python3
"""
Test script for the log web server
"""

import requests
import json
import time
import sys
from pathlib import Path
import pytest

def test_log_server(base_url="http://localhost:8080"):
    """Test the log web server endpoints"""
    
    print(f"Testing log web server at {base_url}")
    print("=" * 50)
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check: OK")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check error (server not reachable): {e}")
        pytest.skip(f"Log server not available: {e}")
    except Exception as e:
        print(f"❌ Health check error: {e}")
        pytest.fail(f"Health check error: {e}")
    
    # Test status endpoint
    try:
        response = requests.get(f"{base_url}/status", timeout=5)
        if response.status_code == 200:
            print("✅ Status endpoint: OK")
            status = response.json()
            print(f"   Coordinator running: {status.get('coordinator_running', 'unknown')}")
            print(f"   Log files: {len(status.get('log_files', {}))}")
        else:
            print(f"❌ Status endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Status endpoint error: {e}")
    
    # Test logs endpoint
    try:
        response = requests.get(f"{base_url}/logs?lines=10", timeout=5)
        if response.status_code == 200:
            print("✅ Logs endpoint: OK")
            logs = response.json()
            print(f"   Log file: {logs.get('log_file')}")
            print(f"   Total lines: {logs.get('total_lines')}")
            print(f"   Returned lines: {logs.get('returned_lines')}")
        else:
            print(f"❌ Logs endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Logs endpoint error: {e}")
    
    # Test log files list
    try:
        response = requests.get(f"{base_url}/logs/files", timeout=5)
        if response.status_code == 200:
            print("✅ Log files list: OK")
            files = response.json()
            print(f"   Available log files: {len(files.get('log_files', []))}")
            for file_info in files.get('log_files', []):
                print(f"     - {file_info['name']} ({file_info['size']} bytes)")
        else:
            print(f"❌ Log files list failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Log files list error: {e}")
    
    # Test dashboard
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ Dashboard: OK")
            print(f"   Content length: {len(response.text)} characters")
        else:
            print(f"❌ Dashboard failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print(f"Dashboard URL: {base_url}")
    print(f"API endpoints:")
    print(f"  - Health: {base_url}/health")
    print(f"  - Status: {base_url}/status")
    print(f"  - Logs: {base_url}/logs")
    print(f"  - Log files: {base_url}/logs/files")
    
    # Test functions should not return values when run under pytest

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    test_log_server(base_url)