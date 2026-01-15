import asyncio
import json
from sqlalchemy.future import select
from .database import AsyncSessionLocal
from .models import Node, Telemetry, CommandAudit, CommandStatus
from .mqtt import mqtt_manager
from .services.market_data import fetch_and_store_prices
from datetime import datetime

async def mqtt_worker():
    """
    Background worker that:
    1. Listens for telemetry (heartbeats).
    2. Listens for events (CMD_ACK, Reconnect).
    3. Triggers periodic price fetching.
    """
    print("🚀 Hub AMQP Worker: Starting...")
    
    # Start periodic tasks
    asyncio.create_task(periodic_price_fetcher())
    
    while True:
        connection = None
        try:
            connection = await mqtt_manager.wait_for_connection()
            channel = await mqtt_manager.get_channel()
            exchange = await mqtt_manager.get_exchange()
            
            # 1. Telemetry Queue
            tele_queue = await channel.declare_queue("hub_telemetry_queue", durable=True)
            await tele_queue.bind(exchange, routing_key="nodes.*.telemetry")
            
            # 2. Events Queue (For ACKs and State reconciliation)
            event_queue = await channel.declare_queue("hub_events_queue", durable=True)
            await event_queue.bind(exchange, routing_key="nodes.*.events")
            
            print(f"✅ Hub AMQP Worker: Bound to telemetry & events")
            
            # Start consumers
            await asyncio.gather(
                consume_messages(tele_queue, process_telemetry, "telemetry"),
                consume_messages(event_queue, process_event, "event")
            )
            
        except Exception as e:
            print(f"❌ Hub AMQP Worker Loop Error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

async def consume_messages(queue, processor, name):
    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                try:
                    routing_key = message.routing_key
                    parts = routing_key.split(".")
                    if len(parts) >= 2:
                        hardware_id = parts[1]
                        payload = json.loads(message.body.decode())
                        await processor(hardware_id, payload)
                except Exception as e:
                    print(f"⚠️ Error in {name} processor: {e}")

async def periodic_price_fetcher():
    """Triggers PSE price fetch every hour."""
    while True:
        print("🕒 Triggering periodic market price fetch...")
        async with AsyncSessionLocal() as session:
            count = await fetch_and_store_prices(session)
            print(f"📈 Price fetcher: Stored {count} points.")
        await asyncio.sleep(3600)

async def process_telemetry(hardware_id: str, data: dict):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(Node).where(Node.hardware_id == hardware_id))
            node = result.scalars().first()
            if not node: return
            
            ts = datetime.utcnow()
            if "timestamp" in data:
                try:
                    ts = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                except: pass

            telemetry = Telemetry(node_id=node.id, timestamp=ts, data=data)
            session.add(telemetry)
            
            node.last_seen = datetime.utcnow()
            node.is_online = True
            
            # GAP REMOVAL: State Reconciliation
            # If node reports a config version that doesn't match DB, we would re-push here
            # (To be implemented when Node-side versioning is ready)
            
            await session.commit()
            # print(f"💾 Telemetry for {hardware_id}")
        except Exception as e:
            await session.rollback()

async def process_event(hardware_id: str, data: dict):
    """Processes node events like CMD_ACK."""
    event_type = data.get("type")
    if event_type == "CMD_ACK":
        cmd_id = data.get("command_id")
        status = data.get("status") # "success" or "error"
        
        async with AsyncSessionLocal() as session:
            try:
                from uuid import UUID
                res = await session.execute(select(CommandAudit).where(CommandAudit.id == UUID(cmd_id)))
                audit = res.scalars().first()
                if audit:
                    audit.status = CommandStatus.acknowledged if status == "success" else CommandStatus.failed
                    await session.commit()
                    print(f"✅ ACK received for command {cmd_id}: {status}")
            except Exception as e:
                print(f"❌ Error processing CMD_ACK: {e}")
                await session.rollback()
