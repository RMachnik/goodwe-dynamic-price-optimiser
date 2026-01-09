import pytest
import requests
import time
import subprocess

@pytest.mark.e2e
def test_mqtt_broker_recovery(mock_node):
    """
    Verify Hub and Edge recover after MQTT broker restart.
    """
    base_url = "http://localhost:8000"
    node_uuid = mock_node
    
    # 1. Login & Check Telemetry Flowing
    login_response = requests.post(
        f"{base_url}/auth/token",
        data={"username": "admin@example.com", "password": "admin123"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Wait for initial telemetry to exist
    print("\n⏳ Waiting for initial telemetry...")
    initial_tel = []
    for _ in range(10):
        initial_tel = requests.get(f"{base_url}/nodes/{node_uuid}/telemetry?limit=1", headers=headers).json()
        if initial_tel:
            break
        time.sleep(2)
        
    last_timestamp = initial_tel[0]["timestamp"] if initial_tel else None
    print(f"📊 Last telemetry timestamp: {last_timestamp}")

    # 2. Kill MQTT Broker
    print("🔥 Killing MQTT Broker...")
    subprocess.run(["docker", "stop", "goodwe-mqtt"], check=True)
    time.sleep(5)
    
    # 3. Start MQTT Broker
    print("♻️ Restarting MQTT Broker...")
    subprocess.run(["docker", "start", "goodwe-mqtt"], check=True)
    
    # 4. Wait for reconnection and see if new data arrives
    print("⏳ Waiting for Hub and Edge to reconnect and sync (60s)...")
    time.sleep(60)
    
    final_tel = requests.get(f"{base_url}/nodes/{node_uuid}/telemetry?limit=1", headers=headers).json()
    new_timestamp = final_tel[0]["timestamp"] if final_tel else None
    print(f"📊 New telemetry timestamp: {new_timestamp}")
    
    assert new_timestamp != last_timestamp, "Telemetry did not resume after MQTT restart"
    print("✅ System recovered from MQTT outage")

@pytest.mark.e2e
def test_db_recovery(docker_stack):
    """
    Verify Hub recovers after Database restart.
    """
    base_url = "http://localhost:8000"
    
    # 1. Check API alive
    resp = requests.get(f"{base_url}/health")
    assert resp.status_code == 200
    
    # 2. Kill DB
    print("\n🔥 Killing Database...")
    subprocess.run(["docker", "stop", "goodwe-db"], check=True)
    time.sleep(3)
    
    # 3. Start DB
    print("♻️ Restarting Database...")
    subprocess.run(["docker", "start", "goodwe-db"], check=True)
    
    # 4. Wait for recovery
    print("⏳ Waiting for Hub to reconnect to DB (10s)...")
    time.sleep(10)
    
    # 5. Verify Hub is ready again
    resp = requests.get(f"{base_url}/readiness")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
    print("✅ Hub recovered from Database outage")
