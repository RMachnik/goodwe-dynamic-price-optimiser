
import asyncio
import os
import aio_pika
import httpx
import json
import logging
from datetime import datetime

# Configuration
API_URL = os.getenv("API_URL", "http://srv26.mikr.us:40314")
AMQP_BROKER = os.getenv("AMQP_BROKER", "mws03.mikr.us")
AMQP_USER = os.getenv("AMQP_USER", "hub_api")
AMQP_PASS = os.getenv("AMQP_PASS", "zeXNCswWHW")
AMQP_PORT = int(os.getenv("AMQP_PORT", 62071))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("E2E_New_Features")

async def get_admin_token():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        payload = {"username": "admin@example.com", "password": "admin123"}
        resp = await client.post(f"{API_URL}/auth/token", data=payload)
        if resp.status_code != 200:
            logger.error(f"Failed to get token: {resp.text}")
            return None
        return resp.json()["access_token"]

async def test_market_prices(token):
    logger.info("🧪 Testing Market Prices Endpoint...")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get(f"{API_URL}/stats/market-prices", headers=headers)
        
        if resp.status_code != 200:
            logger.error(f"❌ /stats/market-prices failed: {resp.status_code}")
            return False
            
        data = resp.json()
        if not isinstance(data, list) or len(data) != 24:
            logger.error(f"❌ Invalid price data format. Expected 24 hours, got {len(data) if isinstance(data, list) else 'invalid'}")
            return False
            
        logger.info(f"✅ Market Prices OK: Retrieved {len(data)} hourly points")
        return True

async def test_node_telemetry_join(token):
    logger.info("🧪 Testing Node Telemetry Join...")
    
    # 1. Provide some dummy telemetry via AMQP first to ensure data exists
    # reusing logic from e2e_stats
    node_hw_id = "e2e-join-test-node"
    
    # Register Node
    async with httpx.AsyncClient(follow_redirects=True) as client:
        headers = {"Authorization": f"Bearer {token}"}
        await client.post(
            f"{API_URL}/nodes", 
            json={"hardware_id": node_hw_id, "name": "Join Test Node", "secret": "secret123"},
            headers=headers
        )
        # Get Node ID
        resp = await client.get(f"{API_URL}/nodes", headers=headers)
        nodes = resp.json()
        target_node = next((n for n in nodes if n["hardware_id"] == node_hw_id), None)
        if not target_node:
            logger.error("❌ Failed to find test node")
            return False
            
        node_id = target_node["id"]
        
    # Send Telemetry
    amqp_url = f"amqp://{AMQP_USER}:{AMQP_PASS}@{AMQP_BROKER}:{AMQP_PORT}/"
    connection = await aio_pika.connect_robust(amqp_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("telemetry", aio_pika.ExchangeType.TOPIC, durable=True)
        
        payload = {
            "node_id": node_id,
            "timestamp": datetime.utcnow().isoformat(),
            "battery": {"soc_percent": 88.5, "voltage": 52.1},
            "solar": {"power_w": 1250},
            "grid": {"current_price": 0.50},
            "optimizer": {"daily_savings_pln": 5.5}
        }
        
        await exchange.publish(
            aio_pika.Message(body=json.dumps(payload).encode()),
            routing_key=f"nodes.{node_hw_id}.telemetry"
        )
        logger.info(f"📤 Sent dummy telemetry for {node_hw_id}")
        
    # Wait for processing
    await asyncio.sleep(2)
    
    # Verify GET /nodes includes telemetry
    async with httpx.AsyncClient(follow_redirects=True) as client:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get(f"{API_URL}/nodes", headers=headers)
        nodes = resp.json()
        target = next((n for n in nodes if n["id"] == node_id), None)
        
        if not target:
            logger.error("❌ Node missing in list response")
            return False
            
        if "latest_telemetry" not in target:
            logger.error("❌ 'latest_telemetry' field missing in NodeResponse")
            return False
            
        t_data = target["latest_telemetry"]
        if not t_data or t_data.get("battery", {}).get("soc_percent") != 88.5:
             logger.error(f"❌ Telemetry data incorrect/missing. Got: {t_data}")
             return False
             
        logger.info("✅ Node Telemetry Join OK: Data correctly merged in list response")
        return True

async def main():
    token = await get_admin_token()
    if not token:
        return
        
    results = await asyncio.gather(
        test_market_prices(token),
        test_node_telemetry_join(token)
    )
    
    if all(results):
        logger.info("🎉 ALL TESTS PASSED")
    else:
        logger.error("💥 SOME TESTS FAILED")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
