import asyncio
import json
import os
import httpx
import aio_pika
from datetime import datetime, timedelta

# Config
AMQP_BROKER = os.getenv("AMQP_BROKER", "mws03.mikr.us")
AMQP_PORT = int(os.getenv("AMQP_PORT", 62071))
AMQP_USER = os.getenv("AMQP_USER", "hub_api")
AMQP_PASS = os.getenv("AMQP_PASS", "zeXNCswWHW")
API_URL = os.getenv("API_URL", "http://srv26.mikr.us:40314") # Default to VPS for now
NODE_ID = "e2e-stats-test-node"

async def publish_telemetry(exchange, node_id, timestamp, savings):
    payload = {
        "node_id": node_id,
        "timestamp": timestamp.isoformat(),
        "battery": {"soc_percent": 50, "voltage": 50},
        "solar": {"power_w": 1000},
        "grid": {"current_price": 0.5, "mode": "IDLE"},
        "optimizer": {"latest_decision": "IDLE", "daily_savings_pln": savings}
    }
    
    routing_key = f"nodes.{node_id}.telemetry"
    message = aio_pika.Message(
        body=json.dumps(payload).encode(),
        content_type="application/json"
    )
    await exchange.publish(message, routing_key=routing_key)
    print(f"📤 Published stats for {timestamp.date()}: {savings} PLN")

async def main():
    print(f"\n🚀 Starting E2E Analytics Test for {NODE_ID}...")
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1. Auth & Register
        print("🔑 Authenticating...")
        token_resp = await client.post(f"{API_URL}/auth/token", data={
            "username": "admin@example.com", "password": "admin123"
        })
        token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Ensure node exists
        await client.post(f"{API_URL}/nodes", headers=headers, json={
            "hardware_id": NODE_ID, "name": "Stats Test Node", "secret": "stats-secret"
        })
        
        # Helper: Get Node UUID
        nodes_resp = await client.get(f"{API_URL}/nodes", headers=headers)
        nodes = nodes_resp.json()
        target_node = next((n for n in nodes if n["hardware_id"] == NODE_ID), None)
        if not target_node:
            print("❌ Initial Node Registration Failed")
            return
        
        node_uuid = target_node["id"]
        print(f"✅ Resolved {NODE_ID} -> {node_uuid}")
        
        # 2. Connect AMQP
        connection = await aio_pika.connect_robust(
             f"amqp://{AMQP_USER}:{AMQP_PASS}@{AMQP_BROKER}:{AMQP_PORT}/"
        )
        
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange("telemetry", aio_pika.ExchangeType.TOPIC, durable=True)
            
            # 3. Publish History (Last 3 days)
            now = datetime.utcnow()
            
            # Day 1 (2 days ago)
            d1 = now - timedelta(days=2)
            await publish_telemetry(exchange, NODE_ID, d1, 10.5)
            
            # Day 2 (Yesterday)
            d2 = now - timedelta(days=1)
            await publish_telemetry(exchange, NODE_ID, d2, 20.0)
            
            # Day 3 (Today)
            await publish_telemetry(exchange, NODE_ID, now, 5.0) # Mid-day
            
            print("⏳ Polling for processed statistics...")
            stats = []
            max_retries = 10
            for i in range(max_retries):
                resp = await client.get(f"{API_URL}/stats/daily-savings/{node_uuid}?days=7", headers=headers)
                if resp.status_code == 200:
                    stats = resp.json()
                    # We expect data for 3 days. 
                    if len(stats) >= 3:
                        print(f"✅ Data consistent after attempt {i+1}")
                        break
                
                print(f"   Attempt {i+1}/{max_retries}: Waiting for aggregation... (got {len(stats)} records)")
                await asyncio.sleep(1)
            
            print(json.dumps(stats, indent=2))
            
            # 5. Assertions
            if len(stats) >= 3:
                # Check for values. Note: stats lists are usually ordered date ASC
                # Filter for our specific dates to ignore potential previous runs
                dates = [s['date'] for s in stats]
                saved = {s['date']: s['savings_pln'] for s in stats}
                
                # Check D1
                d1_str = d1.date().isoformat()
                if d1_str in saved and abs(saved[d1_str] - 10.5) < 0.001:
                    print("✅ Day 1 Savings Correct")
                else:
                    print(f"❌ Day 1 Failed: Expected 10.5, Got {saved.get(d1_str)}")

                # Check D2
                d2_str = d2.date().isoformat()
                if d2_str in saved and abs(saved[d2_str] - 20.0) < 0.001:
                    print("✅ Day 2 Savings Correct")
                else:
                    print(f"❌ Day 2 Failed: Expected 20.0, Got {saved.get(d2_str)}")
                    
                print("🎉 SUCCESS: Analytics E2E Passed!")
            else:
                print(f"❌ FAILURE: Expected at least 3 days of data, got {len(stats)}")

if __name__ == "__main__":
    asyncio.run(main())
