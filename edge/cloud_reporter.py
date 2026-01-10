#!/usr/bin/env python3
import time
import json
import os
import signal
import sys
import logging
import requests
import pika
from datetime import datetime

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("CloudReporter")

# Configuration
def get_config(key, default=None, required=False):
    val = os.getenv(key, default)
    if required and not val:
        logger.fatal(f"Missing required configuration: {key}")
        sys.exit(1)
    return val

AMQP_BROKER = get_config("AMQP_BROKER", "mws03.mikr.us")
AMQP_PORT = int(get_config("AMQP_PORT", 62071))
AMQP_USER = get_config("AMQP_USER", "node_")
AMQP_PASS = get_config("AMQP_PASS", required=True) # Fail if missing
NODE_ID = get_config("NODE_ID", "rasp-01")
LOCAL_API = get_config("LOCAL_API", "http://localhost:8080")
PUBLISH_INTERVAL = int(get_config("PUBLISH_INTERVAL", 60))

class CloudReporter:
    def __init__(self):
        self.running = True
        self.connection = None
        self.channel = None
        
        # Signal Handling
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, signum, frame):
        logger.info("🛑 Received termination signal. Shutting down...")
        self.running = False

    def fetch_telemetry(self):
        """Fetch real data from local coordinator."""
        try:
            # 1. Fetch State
            state_resp = requests.get(f"{LOCAL_API}/current-state", timeout=10)
            state_resp.raise_for_status()
            state = state_resp.json()

            # 2. Fetch Prices
            prices_resp = requests.get(f"{LOCAL_API}/prices", timeout=10)
            prices_resp.raise_for_status()
            prices = prices_resp.json()

            # 3. Construct Payload
            return {
                "node_id": NODE_ID,
                "hw_id": NODE_ID,
                "timestamp": datetime.utcnow().isoformat(),
                "battery": {
                    "soc_percent": state.get("battery_soc", 0),
                    "voltage": state.get("battery_voltage", 0)
                },
                "solar": {
                    "power_w": state.get("pv_power", 0)
                },
                "grid": {
                    "current_price": prices.get("current_price_pln_kwh", 0),
                    "mode": state.get("mode", "UNKNOWN")
                },
                "optimizer": {
                    "latest_decision": state.get("latest_decision", ""),
                    "daily_savings_pln": state.get("daily_savings", 0),
                    "daily_cost_pln": state.get("daily_cost", 0)
                }
            }
        except Exception as e:
            logger.error(f"❌ Fetch error: {e}")
            return None

    def connect(self):
        logger.info(f"📡 Connecting to {AMQP_BROKER}:{AMQP_PORT} as {AMQP_USER}...")
        credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
        parameters = pika.ConnectionParameters(
            host=AMQP_BROKER,
            port=AMQP_PORT,
            virtual_host='/',
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=300
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self.channel.exchange_declare(
            exchange='telemetry', 
            exchange_type='topic', 
            durable=True
        )
        logger.info("✅ Connected to AMQP broker")

    def run(self):
        logger.info(f"🚀 Cloud Reporter starting for {NODE_ID}")
        
        while self.running:
            try:
                if not self.connection or self.connection.is_closed:
                    self.connect()

                while self.running:
                    start_time = time.time()
                    telemetry = self.fetch_telemetry()
                    
                    if telemetry:
                        routing_key = f"nodes.{NODE_ID}.telemetry"
                        payload = json.dumps(telemetry)
                        
                        try:
                            self.channel.basic_publish(
                                exchange='telemetry',
                                routing_key=routing_key,
                                body=payload,
                                properties=pika.BasicProperties(
                                    content_type='application/json',
                                    delivery_mode=2,
                                )
                            )
                            soc = telemetry['battery']['soc_percent']
                            pv = telemetry['solar']['power_w']
                            logger.info(f"📤 Sent telemetry | SOC: {soc}% | PV: {pv}W")
                        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
                            logger.warning(f"⚠️ Connection lost during publish: {e}")
                            break # Break inner loop to reconnect

                    # Sleep logic accounting for time taken
                    elapsed = time.time() - start_time
                    sleep_time = max(0, PUBLISH_INTERVAL - elapsed)
                    
                    # interruptible sleep
                    for _ in range(int(sleep_time * 10)):
                        if not self.running: break
                        time.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}. Retry in 10s...")
                time.sleep(10)
            finally:
                if self.connection and not self.connection.is_closed and not self.running:
                    self.connection.close()
                    logger.info("🔌 Connection closed")

        logger.info("👋 GoodWe Cloud Reporter stopped")

if __name__ == "__main__":
    CloudReporter().run()
