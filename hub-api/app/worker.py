import asyncio
import json
from sqlalchemy.future import select
from .database import AsyncSessionLocal
from .models import Node, Telemetry
from .mqtt import mqtt_manager
from datetime import datetime

async def mqtt_worker():
    """
    Background worker that listens for telemetry.
    """
    print("🚀 Hub MQTT Worker: Starting...")
    
    while True:
        client = None
        try:
            client = await mqtt_manager.wait_for_connection()
            client_id = id(client)
            print(f"📡 Hub MQTT Worker: Using client [ID: {client_id}]")
            
            await asyncio.sleep(1)
            
            print(f"📡 Hub MQTT Worker: Subscribing to telemetry [Client ID: {client_id}]...")
            await client.subscribe("nodes/+/telemetry")
            print(f"✅ Hub MQTT Worker: Subscribed [Client ID: {client_id}]")
            
            async for message in client.messages:
                # print(f"📥 Received on {message.topic}")
                parts = str(message.topic).split("/")
                if len(parts) < 2:
                    continue
                hardware_id = parts[1]
                
                try:
                    payload = json.loads(message.payload.decode())
                    if not isinstance(payload, dict):
                        continue
                    await process_telemetry(hardware_id, payload)
                except Exception as e:
                    print(f"⚠️ Error processing telemetry for {hardware_id}: {e}")
                    
            print(f"📡 Hub MQTT Worker: Message loop ended for [ID: {client_id}]")
            # Notify manager so it reconnects
            mqtt_manager.notify_disconnect(client)
            
        except Exception as e:
            print(f"❌ Hub MQTT Worker Loop Error: {e}. Retrying ingestion loop in 2s...")
            if client:
                mqtt_manager.notify_disconnect(client)
            await asyncio.sleep(2)

async def process_telemetry(hardware_id: str, data: dict):
    async with AsyncSessionLocal() as session:
        try:
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
        except Exception as e:
            print(f"❌ Database error in telemetry processing: {e}")
            await session.rollback()
