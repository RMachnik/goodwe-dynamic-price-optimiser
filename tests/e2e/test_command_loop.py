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
    
    # 1. Login
    login_response = requests.post(
        f"{base_url}/auth/token",
        data={"username": "admin@example.com", "password": "admin123"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Send Command
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
    time.sleep(3)
    
    logs_proc = subprocess.run(
        ["docker", "logs", "goodwe-edge-node"], 
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    logs = logs_proc.stdout
    
    # The mock agent logs: 🎮 [CMD] Received command: {"command_id": "...", "command": "FORCE_CHARGE", ...}
    expected_command_part = f'"command": "FORCE_CHARGE"'
    expected_id_part = f'"command_id": "{cmd_id}"'
    
    assert expected_command_part in logs, f"Mock Agent did not log command type. Logs: {logs}"
    assert expected_id_part in logs, f"Mock Agent did not log command ID. Logs: {logs}"
    print(f"✅ Mock Agent logged receipt of command {cmd_id}")
