import asyncio
import json
from sqlalchemy.future import select
from .database import AsyncSessionLocal
from .models import Node, Telemetry
from .mqtt import mqtt_manager
from datetime import datetime

async def mqtt_worker():
    """
    Background worker that listens for telemetry using the shared MQTT manager.
    """
    print("🚀 Hub MQTT Worker: Starting...")
    
    # Ensure manager is connected (usually handled in lifespan)
    while not mqtt_manager.client:
        await asyncio.sleep(1)
        
    try:
        await mqtt_manager.client.subscribe("nodes/+/telemetry")
        async for message in mqtt_manager.client.messages:
            # Topic: nodes/<hardware_id>/telemetry
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
        print(f"❌ MQTT Worker Error: {e}")

async def process_telemetry(hardware_id: str, data: dict):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Node).where(Node.hardware_id == hardware_id))
        node = result.scalars().first()
        
        if not node:
            return
        
        telemetry = Telemetry(
            node_id=node.id,
            timestamp=datetime.utcnow(),
            data=data
        )
        session.add(telemetry)
        
        node.last_seen = datetime.utcnow()
        node.is_online = True
        
        await session.commit()
        print(f"💾 Persisted telemetry for node {hardware_id}")
