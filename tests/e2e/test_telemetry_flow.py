import pytest
import requests
import time

@pytest.mark.e2e
def test_mock_telemetry_flow(docker_stack):
    """
    Verify the full flow:
    1. Mock Agent (edge-node) publishes telemetry to MQTT.
    2. Hub API (hub-api) receives it via background listener.
    3. We can query it via Hub API endpoint.
    """
    node_id = "mock-node-01"
    url = f"http://localhost:8000/telemetry/{node_id}"
    
    # Wait for data to propagate (Mock agent publishes every 2s)
    max_retries = 15
    data = None
    
    print(f"\n🔍 Waiting for telemetry from {node_id}...")
    for i in range(max_retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Received telemetry at retry {i+1}!")
                break
        except requests.ConnectionError:
            pass
        except Exception as e:
            print(f"ℹ️ Attempt {i+1}: {e}")
            
        time.sleep(2)
    
    assert data is not None, f"Telemetry from {node_id} never reached Hub API"
    assert data["node_id"] == node_id
    assert "battery" in data
    assert data["battery"]["soc_percent"] == 45.5
    print(f"📊 Telemetry data verified: SOC={data['battery']['soc_percent']}%")
