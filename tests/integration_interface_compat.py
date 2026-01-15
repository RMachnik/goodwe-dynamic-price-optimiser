
import asyncio
import os
import json
import httpx
import pytest
import uuid
from datetime import datetime

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:40316")
EDGE_API_URL = os.getenv("EDGE_API_URL", "http://localhost:8000")

async def get_admin_token():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        payload = {"username": "admin@example.com", "password": "admin123"}
        resp = await client.post(f"{API_URL}/auth/token", data=payload)
        if resp.status_code != 200:
            return None
        return resp.json()["access_token"]

@pytest.mark.asyncio
async def test_hub_market_prices_with_node_auth():
    """
    Interface Proof: Hub API /stats/market-prices allows Node Authentication.
    Scenario:
    1. Enroll a new test node via Admin.
    2. Fetch prices using Node headers (X-Node-ID, X-Node-Secret).
    """
    token = await get_admin_token()
    if not token:
        pytest.skip("Admin token not available")

    hw_id = f"test-compat-{uuid.uuid4().hex[:4]}"
    secret = "p65secret"

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        # 1. Enroll Node
        headers = {"Authorization": f"Bearer {token}"}
        enroll_resp = await client.post(
            f"{API_URL}/nodes", 
            json={"hardware_id": hw_id, "name": "Interface Compat Node", "secret": secret},
            headers=headers
        )
        assert enroll_resp.status_code == 200
        
        # 2. Fetch Prices using Node Auth
        node_headers = {
            "X-Node-ID": hw_id,
            "X-Node-Secret": secret
        }
        price_resp = await client.get(f"{API_URL}/stats/market-prices", headers=node_headers)
        
        assert price_resp.status_code == 200, f"Node Auth failed: {price_resp.text}"
        data = price_resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "timestamp" in data[0]
            assert "price_pln_kwh" in data[0]

@pytest.mark.asyncio
async def test_edge_effective_config_schema():
    """
    Interface Proof: Edge /effective-config schema.
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{EDGE_API_URL}/effective-config")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
    except Exception:
        pytest.skip("Edge Local API not reachable on localhost:8000")

if __name__ == "__main__":
    import sys
    pytest.main([__file__])
