import asyncio
import json
import aiomqtt
import os
from sqlalchemy.future import select
from .database import AsyncSessionLocal
from .models import Node, Telemetry
from datetime import datetime

MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

async def mqtt_worker():
    """
    Background worker that subscribes to nodes/+/telemetry and persists data.
    """
    print(f"🚀 Hub MQTT Worker starting (Broker: {MQTT_BROKER})...")
    
    while True:
        try:
            async with aiomqtt.Client(hostname=MQTT_BROKER, port=MQTT_PORT) as client:
                print("✅ Hub MQTT Worker connected")
                await client.subscribe("nodes/+/telemetry")
                
                async for message in client.messages:
                    # Topic format: nodes/<hardware_id>/telemetry
                    parts = message.topic.value.split("/")
                    if len(parts) < 2:
                        continue
                    hardware_id = parts[1]
                    
                    try:
                        payload = json.loads(message.payload.decode())
                        await process_telemetry(hardware_id, payload)
                    except Exception as e:
                        print(f"⚠️ Error processing telemetry for {hardware_id}: {e}")
                        
        except Exception as e:
            print(f"❌ MQTT Worker Connection Error: {e}. Retrying in 10s...")
            await asyncio.sleep(10)

async def process_telemetry(hardware_id: str, data: dict):
    """
    Business logic to link telemetry to nodes and save to DB.
    """
    async with AsyncSessionLocal() as session:
        # 1. Find the Node
        result = await session.execute(select(Node).where(Node.hardware_id == hardware_id))
        node = result.scalars().first()
        
        if not node:
            # For now, we ignore telemetry from unknown nodes
            # In future: Auto-provisioning or logging warning
            return
        
        # 2. Save Telemetry
        telemetry = Telemetry(
            node_id=node.id,
            timestamp=datetime.utcnow(), # Or extract from payload if present
            data=data
        )
        session.add(telemetry)
        
        # 3. Update Node status
        node.last_seen = datetime.utcnow()
        node.is_online = True
        
        await session.commit()
        print(f"💾 Persisted telemetry for node {hardware_id}")
