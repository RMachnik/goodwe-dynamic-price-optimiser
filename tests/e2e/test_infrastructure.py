import pytest
import requests
import time

@pytest.mark.e2e
def test_hub_api_health(docker_stack):
    """
    Verify Hub API is running and returns 200 OK on /health
    """
    url = "http://localhost:8000/health"
    response = requests.get(url)
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "hub-api"

@pytest.mark.e2e
def test_hub_api_readiness(docker_stack):
    """
    Verify Hub API can connect to Postgres and MQTT.
    Values are checked via the /readiness endpoint.
    """
    url = "http://localhost:8000/readiness"
    
    # Retry a few times as DB/MQTT might take a moment to be fully ready even if containers are up
    max_retries = 10
    success = False
    last_response = None
    
    for i in range(max_retries):
        try:
            response = requests.get(url)
            last_response = response
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "ready":
                    success = True
                    break
        except requests.ConnectionError:
            pass
        time.sleep(1)
        
    assert success, f"Hub API Readiness failed. Last response: {last_response.text if last_response else 'None'}"
    
    data = last_response.json()
    assert data["details"]["database"] == "ok"
    assert data["details"]["mqtt"] == "ok"

@pytest.mark.e2e
def test_hub_dashboard_accessible(docker_stack):
    """
    Verify Hub Dashboard (Frontend) is accessible.
    """
    url = "http://localhost:5173"
    try:
        response = requests.get(url)
        assert response.status_code == 200
        assert "<html" in response.text
        assert "hub-dashboard" in response.text
    except requests.ConnectionError:
        pytest.fail("Hub Dashboard is not accessible at http://localhost:5173")
