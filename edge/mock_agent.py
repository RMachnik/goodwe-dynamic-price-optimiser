import asyncio
import json
import os
import aiomqtt
from datetime import datetime

# Configuration from environment
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
NODE_ID = os.getenv("NODE_ID", "mock-node-01")
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", 5))

TELEMETRY_TOPIC = f"nodes/{NODE_ID}/telemetry"
COMMANDS_TOPIC = f"nodes/{NODE_ID}/commands"

async def mqtt_publisher(client):
    while True:
        try:
            payload = {
                "node_id": NODE_ID,
                "timestamp": datetime.now().isoformat(),
                "battery": {
                    "soc_percent": 45.5,
                    "voltage": 52.0
                },
                "solar": {
                    "power_w": 2500
                }
            }
            await client.publish(TELEMETRY_TOPIC, payload=json.dumps(payload))
            print(f"📤 [PUBS] Publishing telemetry to {TELEMETRY_TOPIC}...")
            await asyncio.sleep(PUBLISH_INTERVAL)
        except Exception as e:
            print(f"❌ Publisher Error: {e}")
            break

async def mqtt_subscriber(client):
    try:
        await client.subscribe(COMMANDS_TOPIC)
        print(f"📥 [SUBS] Listening for commands on {COMMANDS_TOPIC}...")
        async for message in client.messages:
            payload = message.payload.decode()
            print(f"🎮 [CMD] Received command: {payload}")
    except Exception as e:
        print(f"❌ Subscriber Error: {e}")

async def main():
    print(f"🚀 Mock Agent {NODE_ID} starting...")
    while True:
        try:
            async with aiomqtt.Client(
                hostname=MQTT_BROKER, 
                port=MQTT_PORT,
                username=MQTT_USER,
                password=MQTT_PASS
            ) as client:
                print("✅ Connected to MQTT broker")
                # Run publisher and subscriber concurrently
                await asyncio.gather(
                    mqtt_publisher(client),
                    mqtt_subscriber(client)
                )
        except Exception as e:
            print(f"❌ MQTT Error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
