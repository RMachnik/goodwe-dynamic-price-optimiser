
import asyncio
import os
import aio_pika
import httpx
import json
import logging
import uuid
from pathlib import Path
from datetime import datetime

# Configuration
API_URL = os.getenv("API_URL", "http://srv26.mikr.us:40314")
AMQP_BROKER = os.getenv("AMQP_BROKER", "mws03.mikr.us")
AMQP_USER = os.getenv("AMQP_USER", "hub_api")
AMQP_PASS = os.getenv("AMQP_PASS", "zeXNCswWHW")
AMQP_PORT = int(os.getenv("AMQP_PORT", 62071))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("E2E_Phase6_5")

async def get_admin_token():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        payload = {"username": "admin@example.com", "password": "admin123"}
        resp = await client.post(f"{API_URL}/auth/token", data=payload)
        if resp.status_code != 200:
            logger.error(f"Failed to get token: {resp.text}")
            return None
        return resp.json()["access_token"]

async def test_layered_config_and_deployment(token):
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {token}"}
        hw_id = f"test-p65-{uuid.uuid4().hex[:4]}"
        logger.info(f"🧪 Testing Phase 6.5 Features for {hw_id}...")

        # 1. Register Node
        resp = await client.post(
            f"{API_URL}/nodes", 
            json={"hardware_id": hw_id, "name": "Phase 6.5 Test Node", "secret": "p65secret"},
            headers=headers
        )
        if resp.status_code != 200:
            logger.error(f"❌ Registration failed: {resp.text}")
            return False
        node_id = resp.json()["id"]

        # 2. Simulate Edge Layered Config Merge
        # We test the logic we added to MasterCoordinator._load_config
        from edge.src.master_coordinator import MasterCoordinator, deep_merge
        
        test_config_dir = Path("/tmp/goodwe_test_config")
        test_config_dir.mkdir(parents=True, exist_ok=True)
        base_file = test_config_dir / "master_coordinator_config.yaml"
        local_file = test_config_dir / "master_coordinator_config_local.yaml"
        override_file = test_config_dir / "override_config.yaml"
        
        import yaml
        with open(base_file, "w") as f:
            yaml.dump({"inverter": {"ip": "1.1.1.1"}, "battery": {"capacity": 10}}, f)
        with open(local_file, "w") as f:
            yaml.dump({"inverter": {"ip": "2.2.2.2"}}, f) # Local override
        with open(override_file, "w") as f:
            yaml.dump({"battery": {"capacity": 20}}, f) # Cloud override
            
        coord = MasterCoordinator(str(base_file))
        merged = coord._load_config()
        
        if merged["inverter"]["ip"] == "2.2.2.2" and merged["battery"]["capacity"] == 20:
            logger.info("✅ Layered Config Merge verified (Base < Local < Override)")
        else:
            logger.error(f"❌ Layered Config Merge FAILED: {merged}")
            return False

        # 3. Simulate DEPLOY command flow
        connection = await aio_pika.connect_robust(
             f"amqp://{AMQP_USER}:{AMQP_PASS}@{AMQP_BROKER}:{AMQP_PORT}/"
        )
        
        async with connection:
            channel = await connection.channel()
            exchange = await channel.get_exchange("telemetry")
            
            queue = await channel.declare_queue(exclusive=True)
            await queue.bind(exchange, routing_key=f"nodes.{hw_id}.commands")
            
            # Send DEPLOY command from Hub
            logger.info("🧪 Scenario: Sending DEPLOY command")
            cmd_payload = {"command": "DEPLOY", "command_id": "test-deploy-id"}
            await client.post(f"{API_URL}/nodes/{node_id}/command", json=cmd_payload, headers=headers)
            
            # Verify Edge receives DEPLOY
            try:
                message = await queue.get(timeout=5)
                async with message.process():
                    body = json.loads(message.body.decode())
                    if body.get("command") == "DEPLOY":
                        logger.info("✅ Edge received DEPLOY command")
                    else:
                        logger.error(f"❌ Received unexpected command: {body}")
                        return False
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for DEPLOY command")
                return False

            # 4. Verify Effective Config Reporting (Loopback)
            # Simulate Edge reporting telemetry including 'reported_config'
            telemetry = {
                "node_id": hw_id,
                "timestamp": datetime.utcnow().isoformat(),
                "battery": {"soc_percent": 50},
                "solar": {"power_w": 0},
                "grid": {"current_price": 0.5},
                "optimizer": {
                    "reported_config": merged # Send the merged config we verified above
                }
            }
            await exchange.publish(
                aio_pika.Message(body=json.dumps(telemetry).encode()),
                routing_key=f"nodes.{hw_id}.telemetry"
            )
            logger.info("📤 Edge reported Effective Config back to Hub")
            
            # Wait for ingestion and check Node Response
            await asyncio.sleep(2)
            resp = await client.get(f"{API_URL}/nodes", headers=headers)
            nodes = resp.json()
            test_node = next((n for n in nodes if n["hardware_id"] == hw_id), None)
            
            if test_node and test_node.get("latest_telemetry", {}).get("optimizer", {}).get("reported_config"):
                conf = test_node["latest_telemetry"]["optimizer"]["reported_config"]
                if conf["inverter"]["ip"] == "2.2.2.2":
                    logger.info("✅ Hub successfully recorded Reported Config loopback")
                else:
                    logger.error(f"❌ Hub recorded wrong config: {conf}")
                    return False
            else:
                logger.error(f"❌ Hub did not record Reported Config. Telemetry: {test_node.get('latest_telemetry')}")
                return False

    return True

async def main():
    token = await get_admin_token()
    if not token:
        return
    
    # Ensure PYTHONPATH includes the edge/src for imports if needed
    import sys
    sys.path.append(os.path.abspath("edge/src"))
    
    result = await test_layered_config_and_deployment(token)
    
    if result:
        logger.info("🎉 PHASE 6.5 E2E TESTS PASSED")
    else:
        logger.error("💥 PHASE 6.5 E2E TESTS FAILED")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
