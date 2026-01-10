import asyncio
import os
import aio_pika
from aio_pika import ExchangeType

# Configuration
AMQP_BROKER = os.getenv("AMQP_BROKER", os.getenv("MQTT_BROKER", "localhost"))
AMQP_PORT = int(os.getenv("AMQP_PORT", os.getenv("MQTT_PORT", 5672)))
AMQP_USER = os.getenv("AMQP_USER", os.getenv("MQTT_USER", "guest"))
AMQP_PASS = os.getenv("AMQP_PASS", os.getenv("MQTT_PASS", "guest"))
AMQP_VHOST = os.getenv("AMQP_VHOST", "/")

class AMQPManager:
    """AMQP connection manager using aio_pika (replaces MQTT)."""
    
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._reconnect_trigger = asyncio.Event()

    @property
    def client(self):
        """Compatibility property for health checks."""
        return self.connection

    async def connect(self):
        """Starts the persistent AMQP connection with reconnection logic."""
        asyncio.create_task(self._connection_loop())

    async def _connection_loop(self):
        amqp_url = f"amqp://{AMQP_USER}:{AMQP_PASS}@{AMQP_BROKER}:{AMQP_PORT}/{AMQP_VHOST}"
        print(f"📡 Hub AMQP Manager: Starting connection loop to {AMQP_BROKER}:{AMQP_PORT} (User: {AMQP_USER})...")
        
        while not self._stop_event.is_set():
            try:
                self.connection = await aio_pika.connect_robust(amqp_url)
                self.channel = await self.connection.channel()
                
                # Declare the telemetry exchange (topic exchange for routing)
                self.exchange = await self.channel.declare_exchange(
                    "telemetry",
                    ExchangeType.TOPIC,
                    durable=True
                )
                
                self._connected_event.set()
                self._reconnect_trigger.clear()
                print(f"✅ Hub AMQP Manager: Connected [ID: {id(self.connection)}]")
                
                # Wait for stop or reconnect signal
                done, pending = await asyncio.wait(
                    [
                        asyncio.create_task(self._stop_event.wait()),
                        asyncio.create_task(self._reconnect_trigger.wait())
                    ],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in pending:
                    task.cancel()
                
                print(f"📡 Hub AMQP Manager: Connection loop cycling [ID: {id(self.connection)}]")
                
                # Close existing connection
                if self.connection and not self.connection.is_closed:
                    await self.connection.close()
                    
            except Exception as e:
                self.connection = None
                self.channel = None
                self.exchange = None
                self._connected_event.clear()
                if not self._stop_event.is_set():
                    print(f"❌ Hub AMQP Manager: Connection failed: {e}. Retrying in 5s...")
                    await asyncio.sleep(5)
            finally:
                self.connection = None
                self.channel = None
                self.exchange = None
                self._connected_event.clear()

    async def disconnect(self):
        self._stop_event.set()
        self._reconnect_trigger.set()
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

    def notify_disconnect(self, failed_connection):
        """Called by workers when they detect the connection is dead."""
        if self.connection and self.connection == failed_connection:
            print(f"⚠️ Hub AMQP Manager: Notified of disconnect for [ID: {id(failed_connection)}]")
            self.connection = None
            self.channel = None
            self.exchange = None
            self._connected_event.clear()
            self._reconnect_trigger.set()

    async def publish(self, routing_key: str, payload: str):
        """Publish message to telemetry exchange."""
        await self.wait_for_connection()
        try:
            message = aio_pika.Message(
                body=payload.encode(),
                content_type="application/json"
            )
            await self.exchange.publish(message, routing_key=routing_key)
            print(f"📤 Published to {routing_key}")
        except Exception as e:
            self.notify_disconnect(self.connection)
            raise

    async def wait_for_connection(self):
        """Blocks until the AMQP connection is established."""
        await self._connected_event.wait()
        return self.connection

    async def get_channel(self):
        """Get the current channel (for workers to create queues)."""
        await self.wait_for_connection()
        return self.channel

    async def get_exchange(self):
        """Get the telemetry exchange."""
        await self.wait_for_connection()
        return self.exchange

# Singleton instance (keeping mqtt_manager name for backward compatibility)
mqtt_manager = AMQPManager()
