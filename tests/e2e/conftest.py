import pytest
import subprocess
import time
import requests
import os

@pytest.fixture(scope="session")
def docker_stack():
    """
    Spins up the full Docker Compose stack for E2E tests.
    """
    print("\n🏗️  Starting Docker Compose stack for E2E tests...")
    # Clean purge first
    subprocess.run(["docker-compose", "down", "-v"], check=True)
    subprocess.run(["docker-compose", "up", "-d", "--build"], check=True)
    
    # NEW: MQTT Security Setup
    print("🔐 Configuring MQTT Security...")
    time.sleep(5) # Wait for mosquitto to start
    subprocess.run([
        "docker", "exec", "goodwe-mqtt", 
        "mosquitto_passwd", "-b", "-c", "/mosquitto/config/password_file", "hub_api", "hub_secret"
    ], check=True)
    subprocess.run([
        "docker", "exec", "goodwe-mqtt", 
        "mosquitto_passwd", "-b", "/mosquitto/config/password_file", "mock-node-01", "secret123"
    ], check=True)
    subprocess.run(["docker", "restart", "goodwe-mqtt"], check=True)

    # Wait for Hub API to be healthy
    base_url = "http://localhost:8000"
    max_retries = 60
    for i in range(max_retries):
        try:
            resp = requests.get(f"{base_url}/health")
            if resp.status_code == 200:
                print("✅ Hub API is healthy!")
                break
        except:
            pass
        time.sleep(1)
    else:
        # Get logs for debugging
        logs = subprocess.run(["docker", "logs", "goodwe-hub-api"], capture_output=True, text=True).stdout
        print(f"DEBUG: Hub API logs:\n{logs}")
        pytest.fail("❌ Hub API failed to start within 60 seconds")
    
    yield
    
    print("\n🗑️  Cleaning up Docker Compose stack...")
    subprocess.run(["docker-compose", "down", "-v"], check=True)

@pytest.fixture
def auth_headers():
    """ Provides admin auth headers for convenience """
    base_url = "http://localhost:8000"
    # Admin is created on startup in hub-api/app/main.py (password: admin123)
    resp = requests.post(f"{base_url}/auth/token", data={
        "username": "admin@example.com",
        "password": "admin123"
    }).json()
    token = resp["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_node(docker_stack, auth_headers):
    """
    Ensures mock-node-01 is enrolled and returns its UUID.
    """
    base_url = "http://localhost:8000"
    hardware_id = "mock-node-01"
    
    # 1. Check if exists
    nodes_resp = requests.get(f"{base_url}/nodes/", headers=auth_headers).json()
    node = next((n for n in nodes_resp if n["hardware_id"] == hardware_id), None)
    
    if not node:
        # 2. Enroll
        print(f"📝 [FIX] Enrolling node {hardware_id} via fixture...")
        enroll_response = requests.post(
            f"{base_url}/nodes/",
            json={
                "hardware_id": hardware_id,
                "secret": "test_secret",
                "name": "E2E Mock Node"
            },
            headers=auth_headers
        )
        node = enroll_response.json()
    
    return node["id"]
