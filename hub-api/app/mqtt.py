import asyncio
import os
import aiomqtt
from contextlib import AsyncExitStack

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")

class MQTTManager:
    def __init__(self):
        self.client = None
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._reconnect_trigger = asyncio.Event()

    async def connect(self):
        """Starts the persistent MQTT client with reconnection logic."""
        asyncio.create_task(self._connection_loop())

    async def _connection_loop(self):
        print(f"📡 Hub MQTT Manager: Starting connection loop to {MQTT_BROKER} (User: {MQTT_USER})...")
        while not self._stop_event.is_set():
            try:
                async with aiomqtt.Client(
                    hostname=MQTT_BROKER, 
                    port=MQTT_PORT,
                    username=MQTT_USER,
                    password=MQTT_PASS
                ) as client:
                    self.client = client
                    self._connected_event.set()
                    self._reconnect_trigger.clear()
                    print(f"✅ Hub MQTT Manager: Connected [ID: {id(client)}]")
                    
                    done, pending = await asyncio.wait(
                        [
                            asyncio.create_task(self._stop_event.wait()),
                            asyncio.create_task(self._reconnect_trigger.wait())
                        ],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    for task in pending:
                        task.cancel()
                    
                    print(f"📡 Hub MQTT Manager: Connection loop cycling [ID: {id(client)}]")
                    
            except Exception as e:
                self.client = None
                self._connected_event.clear()
                if not self._stop_event.is_set():
                    print(f"❌ Hub MQTT Manager: Connection failed: {e}. Retrying in 5s...")
                    await asyncio.sleep(5)
            finally:
                self.client = None
                self._connected_event.clear()

    async def disconnect(self):
        self._stop_event.set()
        self._reconnect_trigger.set()

    def notify_disconnect(self, failed_client):
        """Called by workers when they detect the client is dead."""
        if self.client and self.client == failed_client:
            print(f"⚠️ Hub MQTT Manager: Notified of disconnect for [ID: {id(failed_client)}]")
            self.client = None
            self._connected_event.clear()
            self._reconnect_trigger.set()

    async def publish(self, topic: str, payload: str):
        client = await self.wait_for_connection()
        try:
            await client.publish(topic, payload=payload)
            print(f"📤 Published to {topic}")
        except Exception as e:
            self.notify_disconnect(client)
            raise

    async def wait_for_connection(self):
        """Blocks until the MQTT client is connected."""
        await self._connected_event.wait()
        return self.client

# Singleton instance
mqtt_manager = MQTTManager()
