import asyncio
import json
import os
import httpx
import aio_pika
from datetime import datetime

# Config
AMQP_BROKER = os.getenv("AMQP_BROKER", "mws03.mikr.us")
AMQP_PORT = int(os.getenv("AMQP_PORT", 62071))
AMQP_USER = os.getenv("AMQP_USER", "hub_api")
AMQP_PASS = os.getenv("AMQP_PASS", "zeXNCswWHW")
API_URL = "http://localhost:8000" # Local to container
NODE_ID = "e2e-test-node-async"

async def main():
    print(f"\n🚀 Starting E2E Telemetry Test (Async) for {NODE_ID}...")
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1. Get Token
        print("🔑 Authenticating...")
        resp = await client.post(f"{API_URL}/auth/token", data={
            "username": "admin@example.com",
            "password": "admin123"
        })
        print(f"Auth Resp: {resp.status_code} - {resp.text}")
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Register Node
        print("📝 Registering node...")
        resp = await client.get(f"{API_URL}/nodes", headers=headers)
        print(f"Nodes Resp: {resp.status_code} - {resp.text}")
        nodes = resp.json()
        exists = any(n["hardware_id"] == NODE_ID for n in nodes)
        
        if not exists:
            await client.post(f"{API_URL}/nodes", headers=headers, json={
                "hardware_id": NODE_ID,
                "name": "E2E Async Test Node",
                "secret": "test-secret"
            })
            print("✅ Node registered")
        else:
            print("ℹ️ Node already exists")
            
        # 3. Publish Telemetry via AMQP
        print(f"📡 Connecting to AMQP {AMQP_BROKER}:{AMQP_PORT}...")
        connection = await aio_pika.connect_robust(
            f"amqp://{AMQP_USER}:{AMQP_PASS}@{AMQP_BROKER}:{AMQP_PORT}/"
        )
        
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange("telemetry", aio_pika.ExchangeType.TOPIC, durable=True)
            
            payload = {
                "node_id": NODE_ID,
                "timestamp": datetime.utcnow().isoformat(),
                "battery": {"soc_percent": 88, "voltage": 51.5},
                "solar": {"power_w": 2500},
                "grid": {"current_price": 0.45, "mode": "SELL"},
                "optimizer": {"latest_decision": "DISCHARGE", "daily_savings_pln": 5.5}
            }
            
            routing_key = f"nodes.{NODE_ID}.telemetry"
            message = aio_pika.Message(
                body=json.dumps(payload).encode(),
                content_type="application/json"
            )
            
            await exchange.publish(message, routing_key=routing_key)
            print(f"📤 Published telemetry to {routing_key}")
            
        # 4. Verify
        print("⏳ Waiting 3s for processing...")
        await asyncio.sleep(3)
        
        resp = await client.get(f"{API_URL}/nodes", headers=headers)
        nodes = resp.json()
        target_node = next((n for n in nodes if n["hardware_id"] == NODE_ID), None)
        
        if target_node:
            print(f"✅ Node Status: Online={target_node['is_online']}, Last Seen={target_node['last_seen']}")
            if target_node['is_online']:
                print("🎉 SUCCESS: End-to-End Test Passed!")
            else:
                print("❌ FAILURE: Node is not online")
        else:
            print("❌ FAILURE: Node not found")

if __name__ == "__main__":
    asyncio.run(main())
