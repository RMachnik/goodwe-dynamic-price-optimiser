import asyncio
import json
import os
import time
import aiomqtt

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
NODE_ID = os.getenv("NODE_ID", "mock-node-01")
INTERVAL = int(os.getenv("PUBLISH_INTERVAL", 5))

async def run_agent():
    print(f"🚀 Starting Mock Agent for node: {NODE_ID}")
    print(f"📡 Connecting to broker: {MQTT_BROKER}:{MQTT_PORT}")
    
    while True:
        try:
            async with aiomqtt.Client(hostname=MQTT_BROKER, port=MQTT_PORT) as client:
                print("✅ Connected to MQTT broker")
                while True:
                    # Generate mock telemetry
                    payload = {
                        "node_id": NODE_ID,
                        "timestamp": time.time(),
                        "battery": {
                            "soc_percent": 45.5,
                            "power_kw": 1.2
                        },
                        "photovoltaic": {
                            "power_kw": 3.4
                        },
                        "status": "online"
                    }
                    
                    topic = f"nodes/{NODE_ID}/telemetry"
                    print(f"📤 Publishing telemetry to {topic}...")
                    await client.publish(topic, payload=json.dumps(payload))
                    
                    await asyncio.sleep(INTERVAL)
        except Exception as e:
            print(f"❌ MQTT Error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_agent())
