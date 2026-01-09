import pytest
import subprocess
import time
import os
import requests
from urllib.error import URLError

@pytest.fixture(scope="session")
def docker_stack():
    """
    Fixture to spin up the local Docker stack for E2E tests.
    """
    # 1. Start Docker Stack
    print("\n🐳 Starting Docker Compose stack...")
    subprocess.run(
        ["docker-compose", "up", "-d", "--build"], 
        check=True, 
        cwd=os.getcwd()
    )
    
    # 2. Wait for Health (Simple retry loop)
    # Waiting for Hub API to be responsive
    api_url = "http://localhost:8000/health"
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(api_url)
            if response.status_code == 200:
                print(f"✅ Hub API is healthy! ({response.json()})")
                break
        except requests.exceptions.ConnectionError:
            pass
        
        print(f"⏳ Waiting for Hub API... ({i+1}/{max_retries})")
        time.sleep(1)
    else:
        # Cleanup if failed
        subprocess.run(["docker-compose", "down"], check=True)
        pytest.fail("❌ Hub API failed to start within 30 seconds")
        
    yield
    
    # 3. Teardown
    print("\n🧹 Tearing down Docker stack...")
    # subprocess.run(["docker-compose", "down"], check=True) # Keep running for debug if needed, or uncomment
