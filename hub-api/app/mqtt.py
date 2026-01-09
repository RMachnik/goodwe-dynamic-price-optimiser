import asyncio
import os
import aiomqtt
from contextlib import AsyncExitStack

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

class MQTTManager:
    def __init__(self):
        self.client = None
        self._stack = AsyncExitStack()

    async def connect(self):
        """Starts the persistent MQTT client."""
        print(f"📡 Hub MQTT Manager: Connecting to {MQTT_BROKER}...")
        try:
            self.client = aiomqtt.Client(hostname=MQTT_BROKER, port=MQTT_PORT)
            await self._stack.enter_async_context(self.client)
            print("✅ Hub MQTT Manager: Connected")
        except Exception as e:
            print(f"❌ Hub MQTT Manager: Connection failed: {e}")
            raise

    async def disconnect(self):
        await self._stack.aclose()

    async def publish(self, topic: str, payload: str):
        if not self.client:
            raise RuntimeError("MQTT Client not connected")
        await self.client.publish(topic, payload=payload)
        print(f"📤 Published to {topic}")

    async def get_messages(self):
        if not self.client:
            raise RuntimeError("MQTT Client not connected")
        return self.client.messages

# Singleton instance
mqtt_manager = MQTTManager()
