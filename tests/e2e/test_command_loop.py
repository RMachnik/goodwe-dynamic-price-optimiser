import pytest
import requests
import time
import subprocess

@pytest.mark.e2e
def test_command_loop_execution(docker_stack):
    """
    Verify Hub -> Edge command flow:
    1. API receives POST /command.
    2. API publishes to MQTT.
    3. Mock Agent receives and logs command.
    """
    base_url = "http://localhost:8000"
    hardware_id = "mock-node-01"
    
    # 1. Login
    login_response = requests.post(
        f"{base_url}/auth/token",
        data={"username": "admin@example.com", "password": "admin123"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get Node UUID
    nodes_resp = requests.get(f"{base_url}/nodes/", headers=headers)
    node = next(n for n in nodes_resp.json() if n["hardware_id"] == hardware_id)
    node_uuid = node["id"]
    
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
    # We wait a bit for the mock agent to log it
    print("⏳ Waiting for Mock Agent to log command receipt...")
    time.sleep(3)
    
    logs_proc = subprocess.run(
        ["docker", "logs", "goodwe-edge-node"], 
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    logs = logs_proc.stdout
    
    expected_log = f"Received command: FORCE_CHARGE (ID: {cmd_id})"
    assert expected_log in logs, f"Mock Agent did not log command receipt. Logs: {logs}"
    print(f"✅ Mock Agent logged receipt of command {cmd_id}")
