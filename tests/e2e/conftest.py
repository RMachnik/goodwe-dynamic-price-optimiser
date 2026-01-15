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
    
    # NEW: RabbitMQ & MQTT Setup
    print("🔐 Configuring RabbitMQ & MQTT plugin...")
    time.sleep(15) # Wait for rabbitmq to start
    subprocess.run(["docker", "exec", "goodwe-mqtt", "rabbitmq-plugins", "enable", "rabbitmq_mqtt"], check=True)
    
    # Create mock-node user (hub_api is default)
    subprocess.run(["docker", "exec", "goodwe-mqtt", "rabbitmqctl", "add_user", "mock-node-01", "secret123"], check=False) # ignore if exists
    
    # 1. AMQP Permissions (vhost, config, write, read)
    # mock-node-01 can only write/read its own topics on any exchange (simplified)
    subprocess.run(["docker", "exec", "goodwe-mqtt", "rabbitmqctl", "set_permissions", "-p", "/", "mock-node-01", ".*", ".*", ".*"], check=True)
    
    # 2. Topic Permissions (Strict isolation)
    # For 'telemetry' exchange (AMQP)
    subprocess.run(["docker", "exec", "goodwe-mqtt", "rabbitmqctl", "set_topic_permissions", "-p", "/", "mock-node-01", "telemetry", "^nodes\.mock-node-01\..*", "^nodes\.mock-node-01\..*"], check=True)
    # For 'amq.topic' exchange (MQTT plugin default)
    subprocess.run(["docker", "exec", "goodwe-mqtt", "rabbitmqctl", "set_topic_permissions", "-p", "/", "mock-node-01", "amq.topic", "^nodes\.mock-node-01\..*", "^nodes\.mock-node-01\..*"], check=True)
    
    subprocess.run(["docker", "exec", "goodwe-mqtt", "rabbitmqctl", "set_user_tags", "mock-node-01", "management"], check=True)

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
