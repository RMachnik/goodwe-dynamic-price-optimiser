import asyncio
import json
import os
import aio_pika
from aio_pika import ExchangeType
from datetime import datetime

# Configuration from environment
AMQP_BROKER = os.getenv("MQTT_BROKER", "rabbitmq") # Fallback to rabbitmq service name
AMQP_PORT = int(os.getenv("AMQP_PORT", 5672))
AMQP_USER = os.getenv("MQTT_USER", "mock-node-01")
AMQP_PASS = os.getenv("MQTT_PASS", "secret123")
NODE_ID = os.getenv("NODE_ID", "mock-node-01")
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", 5))

async def amqp_publisher(exchange):
    while True:
        try:
            now = datetime.now()
            hour = now.hour
            is_peak = 18 <= hour <= 21
            is_cheap = 0 <= hour <= 5
            
            soc = 45.0 + (hour % 5) * 10 
            solar_power = 0 if (hour < 6 or hour > 19) else (2500 if 10 <= hour <= 15 else 800)

            payload = {
                "node_id": NODE_ID,
                "timestamp": now.isoformat(),
                "battery": {
                    "soc_percent": soc,
                    "voltage": 52.0 + (soc * 0.05)
                },
                "solar": {
                    "power_w": solar_power
                },
                "grid": {
                    "current_price": 0.85 if is_peak else (0.35 if is_cheap else 0.55),
                    "mode": "DISCHARGING_PROFITABLE" if is_peak else ("CHARGING_ECONOMY" if is_cheap else "PASSIVE")
                },
                "optimizer": {
                    "latest_decision": "Profit Peak: Discharging battery to offset grid" if is_peak else 
                                     ("Economy Mode: Charging at low rate" if is_cheap else "Optimal: Matching load with solar"),
                    "daily_savings_pln": 12.45,
                    "daily_cost_pln": 3.12
                }
            }
            routing_key = f"nodes.{NODE_ID}.telemetry"
            message = aio_pika.Message(
                body=json.dumps(payload).encode(),
                content_type="application/json"
            )
            await exchange.publish(message, routing_key=routing_key)
            print(f"📤 [PUBS] Publishing telemetry to {routing_key}...")
            await asyncio.sleep(PUBLISH_INTERVAL)
        except Exception as e:
            print(f"❌ Publisher Error: {e}")
            break

async def amqp_subscriber(channel, exchange):
    try:
        queue = await channel.declare_queue(f"commands_{NODE_ID}", durable=True, auto_delete=True)
        await queue.bind(exchange, routing_key=f"nodes.{NODE_ID}.commands")
        
        print(f"📥 [SUBS] Listening for commands on nodes.{NODE_ID}.commands...")
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    payload = message.body.decode()
                    print(f"🎮 [CMD] Received command: {payload}")
    except Exception as e:
        print(f"❌ Subscriber Error: {e}")

async def main():
    print(f"🚀 Mock Agent {NODE_ID} starting...")
    amqp_url = f"amqp://{AMQP_USER}:{AMQP_PASS}@{AMQP_BROKER}:{AMQP_PORT}/"
    while True:
        try:
            connection = await aio_pika.connect_robust(amqp_url)
            async with connection:
                channel = await connection.channel()
                exchange = await channel.declare_exchange("telemetry", ExchangeType.TOPIC, durable=True)
                
                print("✅ Connected to AMQP broker")
                await asyncio.gather(
                    amqp_publisher(exchange),
                    amqp_subscriber(channel, exchange)
                )
        except Exception as e:
            print(f"❌ AMQP Error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
