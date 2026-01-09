import pytest
import requests
import time

@pytest.mark.e2e
def test_full_telemetry_loop(docker_stack):
    """
    Verify the full production-like flow:
    1. Login as Admin.
    2. Enroll a new Node.
    3. Mock Agent publishes telemetry via MQTT.
    4. Hub API worker persists telemetry to PostgreSQL.
    5. Query Hub API to verify telemetry exists in DB.
    """
    base_url = "http://localhost:8000"
    hardware_id = "mock-node-01"
    
    # 1. Login
    print("\n🔐 Logging in as admin...")
    login_response = requests.post(
        f"{base_url}/auth/token",
        data={"username": "admin@example.com", "password": "admin123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Enroll Node
    print(f"📝 Enrolling node {hardware_id}...")
    # Check if exists first to make test idempotent
    nodes_response = requests.get(f"{base_url}/nodes/", headers=headers)
    existing_nodes = [n["hardware_id"] for n in nodes_response.json()]
    
    node_uuid = None
    if hardware_id not in existing_nodes:
        enroll_response = requests.post(
            f"{base_url}/nodes/",
            json={
                "hardware_id": hardware_id,
                "secret": "test_secret",
                "name": "E2E Mock Node"
            },
            headers=headers
        )
        assert enroll_response.status_code == 200
        node_uuid = enroll_response.json()["id"]
    else:
        # Get existing ID
        node_uuid = next(n["id"] for n in nodes_response.json() if n["hardware_id"] == hardware_id)
    
    print(f"✅ Node enrolled with ID: {node_uuid}")
    
    # 3. Wait for Telemetry (Mock Agent publishes every 2s)
    # The worker needs to see the node in DB before it starts saving data
    print(f"⏳ Waiting for telemetry to be persisted in DB...")
    max_retries = 15
    data = None
    
    url = f"{base_url}/nodes/{node_uuid}/telemetry"
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                telemetry_list = response.json()
                if len(telemetry_list) > 0:
                    data = telemetry_list[0]["data"]
                    print(f"📊 Telemetry received! (Retries: {i+1})")
                    break
        except Exception as e:
            print(f"ℹ️ Attempt {i+1}: {e}")
            
        time.sleep(2)
        
    assert data is not None, f"Telemetry for {hardware_id} never reached the database"
    assert data["node_id"] == hardware_id
    assert data["battery"]["soc_percent"] == 45.5
    print(f"🎯 Full Loop Verified: Edge -> MQTT -> Hub -> PostgreSQL -> API ✅")
