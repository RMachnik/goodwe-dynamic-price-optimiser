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
            # Simulate dynamic energy states
            now = datetime.now()
            hour = now.hour
            is_peak = 18 <= hour <= 21
            is_cheap = 0 <= hour <= 5
            
            soc = 45.0 + (hour % 5) * 10 # Mock SOC fluctuation
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
