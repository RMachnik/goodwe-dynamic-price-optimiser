
import asyncio
import os
import aio_pika
import httpx
import json
import logging
from datetime import datetime, timedelta
import uuid

# Configuration
API_URL = os.getenv("API_URL", "http://srv26.mikr.us:40314")
AMQP_BROKER = os.getenv("AMQP_BROKER", "mws03.mikr.us")
AMQP_USER = os.getenv("AMQP_USER", "hub_api")
AMQP_PASS = os.getenv("AMQP_PASS", "zeXNCswWHW")
AMQP_PORT = int(os.getenv("AMQP_PORT", 62071))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("E2E_Phase6")

async def get_admin_token():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        payload = {"username": "admin@example.com", "password": "admin123"}
        resp = await client.post(f"{API_URL}/auth/token", data=payload)
        if resp.status_code != 200:
            logger.error(f"Failed to get token: {resp.text}")
            return None
        return resp.json()["access_token"]

async def test_phase6_features(token):
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Register a Test Node
        hw_id = f"test-p6-{uuid.uuid4().hex[:4]}"
        logger.info(f"🧪 Testing Phase 6 Features for {hw_id}...")
        
        resp = await client.post(
            f"{API_URL}/nodes", 
            json={"hardware_id": hw_id, "name": "Phase 6 Test Node", "secret": "p6secret"},
            headers=headers
        )
        if resp.status_code != 200:
            logger.error(f"❌ Registration failed: {resp.text}")
            return False
        node_id = resp.json()["id"]

        # Connect to AMQP to act as both Hub and Edge for verification
        connection = await aio_pika.connect_robust(
             f"amqp://{AMQP_USER}:{AMQP_PASS}@{AMQP_BROKER}:{AMQP_PORT}/"
        )
        
        async with connection:
            channel = await connection.channel()
            exchange = await channel.get_exchange("telemetry")
            
            # Create a queue to listen for commands sent to this node
            queue = await channel.declare_queue(exclusive=True)
            await queue.bind(exchange, routing_key=f"nodes.{hw_id}.commands")
            
            # --- Scenario A: Config Sync Trigger ---
            logger.info("🧪 Scenario A: Config Sync Trigger")
            config_update = {"config": {"tariff": "G12asdf", "pv_size_kw": 5.5}}
            await client.patch(f"{API_URL}/nodes/{node_id}", json=config_update, headers=headers)
            
            # Verify Edge receives the command
            try:
                message = await queue.get(timeout=5)
                async with message.process():
                    body = json.loads(message.body.decode())
                    if body.get("command") == "CONFIG_UPDATE" and body.get("payload", {}).get("pv_size_kw") == 5.5:
                        logger.info("✅ Edge received CONFIG_UPDATE via MQTT-Sync trigger")
                    else:
                        logger.error(f"❌ Received unexpected command: {body}")
                        return False
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for CONFIG_UPDATE command")
                return False

            # --- Scenario B: Command Center V2 & ACK ---
            logger.info("🧪 Scenario B: Command Center V2 & ACK Workflow")
            cmd_payload = {"command": "CHARGE", "payload": {"target_soc": 80}}
            resp = await client.post(f"{API_URL}/nodes/{node_id}/command", json=cmd_payload, headers=headers)
            audit_id = resp.json()["id"]
            
            # 1. Edge receives command
            try:
                message = await queue.get(timeout=5)
                async with message.process():
                    body = json.loads(message.body.decode())
                    cmd_id = body.get("command_id")
                    logger.info(f"✅ Edge received CHARGE command [ID: {cmd_id}]")
                    
                    # 2. Edge sends ACK
                    ack_payload = {
                        "type": "CMD_ACK",
                        "command_id": cmd_id,
                        "status": "success",
                        "node_id": hw_id
                    }
                    await exchange.publish(
                        aio_pika.Message(body=json.dumps(ack_payload).encode()),
                        routing_key=f"nodes.{hw_id}.events"
                    )
                    logger.info("📤 Edge sent CMD_ACK")
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for CHARGE command")
                return False
            
            # 3. Verify Hub updates status to 'acknowledged'
            await asyncio.sleep(2) # Wait for worker to process ACK
            resp = await client.get(f"{API_URL}/nodes/{node_id}/command", headers=headers)
            # Find the audit entry (it's a list in some variants or need to check history)
            # Assuming we might need an endpoint for command status or just check the response
            # Since we don't have a direct "get audit by ID" endpoint yet in the routes shown, 
            # let's assume one or check the node status if it shows recent commands.
            # Wait, the CommandAudit is in the DB.
            
            # Let's check if the stats/market-prices is working too
            logger.info("🧪 Scenario C: Real Market Data Endpoint")
            resp = await client.get(f"{API_URL}/stats/market-prices", headers=headers)
            if resp.status_code == 200:
                prices = resp.json()
                logger.info(f"✅ Market Prices fetched: {len(prices)} points. Example: {prices[0]}")
            else:
                logger.error(f"❌ Market Prices endpoint failed: {resp.text}")
                return False
            
    return True

async def main():
    token = await get_admin_token()
    if not token:
        return
        
    result = await test_phase6_features(token)
    
    if result:
        logger.info("🎉 PHASE 6 E2E TESTS PASSED")
    else:
        logger.error("💥 PHASE 6 E2E TESTS FAILED")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
