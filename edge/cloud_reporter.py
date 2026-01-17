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

import threading

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

            # 2. Fetch Prices & Config (Observed State)
            prices = {}
            try:
                # Prices might fail if pseudo-duck-curve is used or collector is down
                prices_resp = requests.get(f"{LOCAL_API}/prices", timeout=10)
                if prices_resp.ok:
                    prices = prices_resp.json()
            except: pass

            config = {}
            try:
                # 🛡️ GAP REMOVAL: Reporting Effective Config
                config_resp = requests.get(f"{LOCAL_API}/effective-config", timeout=10)
                if config_resp.ok:
                    config = config_resp.json()
            except: pass

            # 3. Extract data from nested structure
            battery_data = state.get("battery", {})
            pv_data = state.get("photovoltaic", {})
            pricing_data = state.get("pricing", {})
            recommendations = state.get("recommendations", {})
            
            # 4. Construct Payload
            return {
                "node_id": NODE_ID,
                "hw_id": NODE_ID,
                "timestamp": datetime.utcnow().isoformat(),
                "battery": {
                    "soc_percent": battery_data.get("soc_percent", 0),
                    "voltage": battery_data.get("voltage", 0),
                    "temperature_c": battery_data.get("temperature_c", 0)
                },
                "solar": {
                    "power_w": pv_data.get("current_power_w", 0)
                },
                "grid": {
                    "current_price": pricing_data.get("current_price_pln_kwh", 0),
                    "mode": recommendations.get("primary_action", "UNKNOWN")
                },
                "optimizer": {
                    "latest_decision": recommendations.get("primary_action", ""),
                    "daily_savings_pln": state.get("daily_savings", 0),
                    "daily_cost_pln": state.get("daily_cost", 0),
                    "reported_config": config # The loop-back verification
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
        
        # Declare Exchanges
        self.channel.exchange_declare(
            exchange='telemetry', 
            exchange_type='topic', 
            durable=True
        )
        logger.info("✅ Connected to AMQP broker")

    def on_command(self, ch, method, properties, body):
        """Callback when a command is received from the cloud."""
        try:
            data = json.loads(body)
            cmd_id = data.get("command_id", "NO_ID")
            command = data.get("command")
            payload = data.get("payload", {})
            
            logger.info(f"📥 Received Command: {command} [ID: {cmd_id}]")
            
            success = False
            response_data = {}
            
            # Dispatch to local API
            if command == "CONFIG_UPDATE":
                resp = requests.post(f"{LOCAL_API}/config", json=payload, timeout=10)
                success = resp.ok
            elif command == "DEPLOY":
                # Trigger self-update (deferred by 5s inside the log-server)
                resp = requests.post(f"{LOCAL_API}/deploy", json=payload, timeout=10)
                success = resp.ok
            else:
                # CHARGE, DISCHARGE, AUTO, etc.
                resp = requests.post(f"{LOCAL_API}/control", json={"command": command, "payload": payload}, timeout=10)
                success = resp.ok
            
            # 💡 GAP REMOVAL: Send ACK
            ack_payload = {
                "type": "CMD_ACK",
                "command_id": cmd_id,
                "status": "success" if success else "error",
                "node_id": NODE_ID
            }
            ch.basic_publish(
                exchange='telemetry',
                routing_key=f"nodes.{NODE_ID}.events",
                body=json.dumps(ack_payload)
            )
            logger.info(f"📤 Sent ACK for {cmd_id}: {'Success' if success else 'Failed'}")
            
        except Exception as e:
            logger.error(f"❌ Error in on_command: {e}")

    def run_command_consumer(self):
        """Runs in a separate thread to listen for commands."""
        while self.running:
            try:
                # We need a separate connection for the consumer to avoid thread safety issues with pika
                credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
                params = pika.ConnectionParameters(host=AMQP_BROKER, port=AMQP_PORT, credentials=credentials, heartbeat=60)
                conn = pika.BlockingConnection(params)
                channel = conn.channel()
                
                # Create a temporary queue for this node's commands
                queue_name = f"commands_{NODE_ID}"
                channel.queue_declare(queue=queue_name, durable=True, auto_delete=True)
                channel.queue_bind(queue=queue_name, exchange='telemetry', routing_key=f"nodes.{NODE_ID}.commands")
                
                channel.basic_consume(queue=queue_name, on_message_callback=self.on_command, auto_ack=True)
                
                logger.info(f"👂 Command consumer started for nodes.{NODE_ID}.commands")
                while self.running and not conn.is_closed:
                    conn.process_data_events(time_limit=1)
                
                if not conn.is_closed: conn.close()
            except Exception as e:
                logger.error(f"❌ Command consumer error: {e}. Retrying in 10s...")
                time.sleep(10)

    def run(self):
        logger.info(f"🚀 Cloud Reporter starting for {NODE_ID}")
        
        # Start command consumer thread
        cmd_thread = threading.Thread(target=self.run_command_consumer, daemon=True)
        cmd_thread.start()
        
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
                            logger.info(f"📤 Sent telemetry | SOC: {telemetry['battery']['soc_percent']}%")
                        except Exception as e:
                            logger.warning(f"⚠️ Publish error: {e}")
                            break # Reconnect

                    # Sleep logic accounting for time taken
                    elapsed = time.time() - start_time
                    sleep_time = max(0, PUBLISH_INTERVAL - elapsed)
                    
                    # interruptible sleep
                    for _ in range(int(sleep_time * 10)):
                        if not self.running: break
                        time.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ Main loop error: {e}. Retry in 10s...")
                time.sleep(10)
            finally:
                if self.connection and not self.connection.is_closed:
                    self.connection.close()
                    logger.info("🔌 Connection closed")

        logger.info("👋 GoodWe Cloud Reporter stopped")

if __name__ == "__main__":
    CloudReporter().run()
