import asyncio
import json
from sqlalchemy.future import select
from .database import AsyncSessionLocal
from .models import Node, Telemetry
from .mqtt import mqtt_manager
from datetime import datetime

async def mqtt_worker():
    """
    Background worker that listens for telemetry via AMQP.
    """
    print("🚀 Hub AMQP Worker: Starting...")
    
    while True:
        connection = None
        try:
            # Wait for connection
            connection = await mqtt_manager.wait_for_connection()
            channel = await mqtt_manager.get_channel()
            exchange = await mqtt_manager.get_exchange()
            connection_id = id(connection)
            
            print(f"📡 Hub AMQP Worker: Using connection [ID: {connection_id}]")
            
            # Create a queue for this worker to receive telemetry
            queue = await channel.declare_queue(
                "hub_telemetry_queue",
                durable=True
            )
            
            # Bind to telemetry exchange with wildcard routing key
            # nodes.*.telemetry will match nodes.node01.telemetry, nodes.rasp-01.telemetry, etc.
            await queue.bind(exchange, routing_key="nodes.*.telemetry")
            print(f"✅ Hub AMQP Worker: Bound to telemetry exchange [Connection ID: {connection_id}]")
            
            # Consume messages
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            # Extract hardware_id from routing key (nodes.{hardware_id}.telemetry)
                            routing_key = message.routing_key
                            parts = routing_key.split(".")
                            if len(parts) >= 2:
                                hardware_id = parts[1]
                                payload = json.loads(message.body.decode())
                                if isinstance(payload, dict):
                                    await process_telemetry(hardware_id, payload)
                        except Exception as e:
                            print(f"⚠️ Error processing telemetry: {e}")
            
            print(f"📡 Hub AMQP Worker: Message loop ended for [ID: {connection_id}]")
            mqtt_manager.notify_disconnect(connection)
            
        except Exception as e:
            print(f"❌ Hub AMQP Worker Loop Error: {e}. Retrying in 2s...")
            if connection:
                mqtt_manager.notify_disconnect(connection)
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
