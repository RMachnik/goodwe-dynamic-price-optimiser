
import asyncio
import os
import aio_pika
import httpx
import json
import logging
from datetime import datetime
import uuid

# Configuration
API_URL = os.getenv("API_URL", "http://srv26.mikr.us:40314")
AMQP_BROKER = os.getenv("AMQP_BROKER", "mws03.mikr.us")
AMQP_USER = os.getenv("AMQP_USER", "hub_api")
AMQP_PASS = os.getenv("AMQP_PASS", "zeXNCswWHW")
AMQP_PORT = int(os.getenv("AMQP_PORT", 62071))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("E2E_Full")

async def get_admin_token():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        payload = {"username": "admin@example.com", "password": "admin123"}
        resp = await client.post(f"{API_URL}/auth/token", data=payload)
        if resp.status_code != 200:
            logger.error(f"Failed to get token: {resp.text}")
            return None
        return resp.json()["access_token"]

async def test_node_lifecycle(token):
    async with httpx.AsyncClient(follow_redirects=True) as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Register Node
        hw_id = f"test-node-{uuid.uuid4().hex[:8]}"
        logger.info(f"🧪 Testing Node Lifecycle for {hw_id}...")
        
        resp = await client.post(
            f"{API_URL}/nodes", 
            json={"hardware_id": hw_id, "name": "E2E Lifecycle Node", "secret": "secret123"},
            headers=headers
        )
        if resp.status_code != 200:
            logger.error(f"❌ Registration failed: {resp.text}")
            return False
        
        node_id = resp.json()["id"]
        logger.info(f"✅ Node Registered: {node_id}")
        
        # 2. Update Config (PATCH)
        logger.info("🧪 Testing Config Update (PATCH)...")
        config_payload = {
            "config": {
                "tariff": "G12W",
                "pv_size_kw": 10.5,
                "bat_capacity_kwh": 20
            }
        }
        resp = await client.patch(f"{API_URL}/nodes/{node_id}", json=config_payload, headers=headers)
        if resp.status_code != 200:
            logger.error(f"❌ Config update failed: {resp.text}")
            return False
            
        updated_node = resp.json()
        if updated_node["config"]["tariff"] != "G12W":
            logger.error(f"❌ Config mismatch. Got: {updated_node['config']}")
            return False
        logger.info("✅ Config Update Verified")
        
        # 3. Send Command (POST)
        logger.info("🧪 Testing Command Dispatch...")
        cmd_payload = {"command": "CHARGE", "payload": {"target_soc": 100}}
        resp = await client.post(f"{API_URL}/nodes/{node_id}/command", json=cmd_payload, headers=headers)
        
        if resp.status_code not in [200, 202]:
            logger.error(f"❌ Command failed: {resp.text}")
            return False
            
        audit = resp.json()
        if audit["status"] not in ["sent", "pending"]:
             logger.error(f"❌ Command status invalid: {audit['status']}")
             return False
        logger.info(f"✅ Command Sent (Audit ID: {audit['id']})")
        
        # 4. Telemetry Join (AMQP Injection)
        logger.info("🧪 Testing Telemetry Injection...")
        connection = await aio_pika.connect_robust(
             f"amqp://{AMQP_USER}:{AMQP_PASS}@{AMQP_BROKER}:{AMQP_PORT}/"
        )
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange("telemetry", aio_pika.ExchangeType.TOPIC, durable=True)
            
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "battery": {"soc_percent": 42.0},
                "solar": {"power_w": 999}
            }
            
            await exchange.publish(
                aio_pika.Message(body=json.dumps(payload).encode()),
                routing_key=f"nodes.{hw_id}.telemetry"
            )
            logger.info("📤 Telemetry Published")
            
        await asyncio.sleep(2) # Wait for worker
        
        # Verify
        resp = await client.get(f"{API_URL}/nodes", headers=headers)
        nodes = resp.json()
        target = next((n for n in nodes if n["id"] == node_id), None)
        
        if not target or target.get("latest_telemetry", {}).get("battery", {}).get("soc_percent") != 42.0:
            logger.error(f"❌ Telemetry verification failed. Data: {target.get('latest_telemetry') if target else 'Node Missing'}")
            return False
            
        logger.info("✅ Telemetry Verified")
        return True

async def main():
    token = await get_admin_token()
    if not token:
        return
        
    result = await test_node_lifecycle(token)
    
    if result:
        logger.info("🎉 FULL E2E SUITE PASSED")
    else:
        logger.error("💥 TEST SUITE FAILED")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
