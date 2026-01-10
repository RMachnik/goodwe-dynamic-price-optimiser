import pytest
import requests
import time

@pytest.mark.e2e
def test_full_telemetry_loop(mock_node):
    """
    Verify the full production-like flow using standard payload.
    """
    base_url = "http://localhost:8000"
    hardware_id = "mock-node-01"
    node_uuid = mock_node
    
    # 1. Login
    print("\n🔐 Logging in as admin...")
    login_response = requests.post(
        f"{base_url}/auth/token",
        data={"username": "admin@example.com", "password": "admin123"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Wait for Telemetry
    print(f"⏳ Waiting for telemetry to be persisted in DB...")
    max_retries = 20
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
    # Verify telemetry structure and enriched data
    assert "battery" in data
    assert "solar" in data
    assert "grid" in data  # New enriched field
    assert "optimizer" in data  # New enriched field
    assert data["battery"]["soc_percent"] >= 0 and data["battery"]["soc_percent"] <= 100
    assert data["battery"]["voltage"] > 0
    assert "current_price" in data["grid"]
    assert "daily_savings_pln" in data["optimizer"]
    print(f"🎯 Full Loop Verified: Edge -> MQTT -> Hub -> PostgreSQL -> API ✅")
