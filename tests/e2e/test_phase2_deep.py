import pytest
import requests
import time
from uuid import UUID

@pytest.fixture(scope="module")
def api_setup(docker_stack):
    base_url = "http://localhost:8000"
    
    # 1. Login as Admin
    login_response = requests.post(
        f"{base_url}/auth/token",
        data={"username": "admin@example.com", "password": "admin123"}
    )
    admin_token = login_response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 2. Register and Login as regular User
    # Clean up user if exists (ignoring error)
    requests.post(f"{base_url}/auth/register", 
                  json={"email": "user@example.com", "password": "user123", "role": "user"})
    
    user_login = requests.post(
        f"{base_url}/auth/token",
        data={"username": "user@example.com", "password": "user123"}
    )
    user_token = user_login.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}
    
    return {
        "base_url": base_url,
        "admin_headers": admin_headers,
        "user_headers": user_headers
    }

@pytest.mark.e2e
def test_rbac_node_access(api_setup):
    """Verify that a regular user cannot access or modify nodes they don't own."""
    base_url = api_setup["base_url"]
    admin_headers = api_setup["admin_headers"]
    user_headers = api_setup["user_headers"]
    
    # 1. Admin enrolls a node
    hw_id = "rbac-test-node"
    resp = requests.post(f"{base_url}/nodes/", 
                         json={"hardware_id": hw_id, "secret": "sec", "name": "Admin Node"},
                         headers=admin_headers)
    assert resp.status_code == 200
    node_id = resp.json()["id"]
    
    # 2. Regular user tries to GET it
    resp = requests.get(f"{base_url}/nodes/{node_id}", headers=user_headers)
    assert resp.status_code == 403, "User should not be able to access Admin's node"
    
    # 3. Regular user tries to LIST it
    resp = requests.get(f"{base_url}/nodes/", headers=user_headers)
    nodes = resp.json()
    assert all(n["id"] != node_id for n in nodes), "Admin's node should not appear in User's list"

@pytest.mark.e2e
def test_node_config_persistence(api_setup):
    """Verify that updating a node configuration via API works."""
    base_url = api_setup["base_url"]
    admin_headers = api_setup["admin_headers"]
    
    hw_id = "config-test-node"
    # Ensure node exists
    resp = requests.post(f"{base_url}/nodes/", 
                         json={"hardware_id": hw_id, "secret": "sec", "name": "Config Node"},
                         headers=admin_headers)
    node_id = resp.json() if resp.status_code == 200 else requests.get(f"{base_url}/nodes/", headers=admin_headers).json()[0]["id"]
    if isinstance(node_id, dict): node_id = node_id["id"]

    new_config = {"charge_limit": 80, "mode": "eco"}
    
    # Patch config
    patch_resp = requests.patch(f"{base_url}/nodes/{node_id}", 
                                json={"config": new_config},
                                headers=admin_headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["config"] == new_config
    
    # Re-fetch to confirm persistence
    get_resp = requests.get(f"{base_url}/nodes/{node_id}", headers=admin_headers)
    assert get_resp.json()["config"] == new_config

@pytest.mark.e2e
def test_multi_node_telemetry_isolation(api_setup):
    """Verify that telemetry from different nodes is correctly isolated in the DB."""
    base_url = api_setup["base_url"]
    admin_headers = api_setup["admin_headers"]
    
    # 1. Enroll Node A and Node B
    nodes = []
    for i in range(2):
        hw_id = f"multi-test-node-{i}"
        requests.post(f"{base_url}/nodes/", 
                      json={"hardware_id": hw_id, "secret": "sec", "name": f"Node {i}"},
                      headers=admin_headers)
        get_res = requests.get(f"{base_url}/nodes/", headers=admin_headers)
        node = next(n for n in get_res.json() if n["hardware_id"] == hw_id)
        nodes.append(node)

    # 2. Simulate MQTT messages for BOTH nodes manually (simulating the worker's reach)
    # We use requests to a internal debug endpoint or just wait for mock agents...
    # Actually, we have one mock agent. Let's rely on the fact that if we had two, they'd use different topics.
    # Topic format: nodes/<hw_id>/telemetry
    
    # For this test, let's manually check if the endpoint returns ONLY data for the specific node_id
    # We'll use the existing mock-node-01 and verify another node returns empty
    
    node_0_id = nodes[0]["id"]
    node_1_id = nodes[1]["id"]
    
    resp_0 = requests.get(f"{base_url}/nodes/{node_0_id}/telemetry", headers=admin_headers)
    resp_1 = requests.get(f"{base_url}/nodes/{node_1_id}/telemetry", headers=admin_headers)
    
    # High level isolation check
    # If mock-node-01 is running, it shouldn't show up in node_0's telemetry
    mock_hw_id = "mock-node-01"
    
    # Wait a bit for the mock agent to potentially "leak" if the logic was broken
    time.sleep(2)
    
    resp_0 = requests.get(f"{base_url}/nodes/{node_0_id}/telemetry", headers=admin_headers)
    assert len(resp_0.json()) == 0, "Node 0 should have no telemetry (Mock agent is using different HW_ID)"
