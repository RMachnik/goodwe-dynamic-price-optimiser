import pytest
import requests
import time
import subprocess

@pytest.mark.e2e
def test_command_loop_execution(mock_node):
    """
    Verify Hub -> Edge command flow:
    1. API receives POST /command.
    2. API publishes to MQTT.
    3. Mock Agent receives and logs command.
    """
    base_url = "http://localhost:8000"
    hardware_id = "mock-node-01"
    node_uuid = mock_node
    
    # 2. Login
    login_response = requests.post(
        f"{base_url}/auth/token",
        data={"username": "admin@example.com", "password": "admin123"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # NEW: Wait for Mock Agent to be connected
    print(f"⏳ Waiting for {hardware_id} to connect to RabbitMQ...")
    for i in range(15):
        logs = subprocess.run(["docker", "logs", "goodwe-edge-node"], capture_output=True, text=True).stdout
        if "Connected to AMQP broker" in logs:
            print("✅ Mock Agent is connected.")
            break
        time.sleep(2)
    else:
        pytest.fail("Mock Agent never connected to broker")
    print(f"\n⚡ Sending 'FORCE_CHARGE' command to {hardware_id}...")
    cmd_payload = {"power_kw": 2.5}
    resp = requests.post(
        f"{base_url}/nodes/{node_uuid}/command/",
        json={"command": "FORCE_CHARGE", "payload": cmd_payload},
        headers=headers
    )
    assert resp.status_code == 202
    audit_data = resp.json()
    assert audit_data["status"] == "sent"
    cmd_id = audit_data["id"]
    
    # 4. Check Edge Logs (Verify receipt)
    print("⏳ Waiting for Mock Agent to log command receipt...")
    
    max_log_retries = 10
    command_received = False
    logs = ""
    
    for i in range(max_log_retries):
        time.sleep(2)
        logs_proc = subprocess.run(
            ["docker", "logs", "goodwe-edge-node"], 
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        logs = logs_proc.stdout
        
        expected_command_part = f'"command": "FORCE_CHARGE"'
        if expected_command_part in logs:
            command_received = True
            break
        print(f"  (Attempt {i+1}/{max_log_retries}) Still waiting for command in logs...")

    assert command_received, f"Mock Agent did not log command receipt within timeout. Logs: {logs}"
    print(f"✅ Mock Agent logged receipt of command")
