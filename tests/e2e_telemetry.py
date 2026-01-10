import os
import json
import time
import requests
import pika
import unittest
from datetime import datetime

# Config
AMQP_BROKER = os.getenv("AMQP_BROKER", "mws03.mikr.us")
AMQP_PORT = int(os.getenv("AMQP_PORT", 62071))
AMQP_USER = os.getenv("AMQP_USER", "node_")
AMQP_PASS = os.getenv("AMQP_PASS", "change_me") # User must provide this
API_URL = os.getenv("API_URL", "http://srv26.mikr.us:40314")
NODE_ID = "e2e-test-node"

class TestTelemetryFlow(unittest.TestCase):
    def setUp(self):
        # 1. Register test node if not exists
        token = self.get_admin_token()
        self.register_node(token)

    def get_admin_token(self):
        resp = requests.post(f"{API_URL}/auth/token", data={
            "username": "admin@example.com",
            "password": "admin123"
        })
        if resp.status_code != 200:
            self.skipTest("API Auth failed")
        return resp.json()["access_token"]

    def register_node(self, token):
        headers = {"Authorization": f"Bearer {token}"}
        # Check if node exists
        resp = requests.get(f"{API_URL}/nodes", headers=headers)
        nodes = resp.json()
        for node in nodes:
            if node["hardware_id"] == NODE_ID:
                return # Already exists
        
        # Create
        requests.post(f"{API_URL}/nodes", headers=headers, json={
            "hardware_id": NODE_ID,
            "name": "E2E Test Node",
            "secret": "test-secret"
        })

    def test_telemetry_publish_consume(self):
        print(f"\n🚀 Starting E2E Telemetry Test for {NODE_ID}...")
        
        # 1. Connect to RabbitMQ
        credentials = pika.PlainCredentials(AMQP_USER, AMQP_PASS)
        parameters = pika.ConnectionParameters(
            host=AMQP_BROKER,
            port=AMQP_PORT,
            virtual_host='/',
            credentials=credentials
        )
        
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.exchange_declare(exchange='telemetry', exchange_type='topic', durable=True)
        except Exception as e:
            self.fail(f"RabbitMQ Connection failed: {e}")

        # 2. Publish Telemetry
        payload = {
            "node_id": NODE_ID,
            "timestamp": datetime.utcnow().isoformat(),
            "battery": {"soc_percent": 99, "voltage": 52.5},
            "solar": {"power_w": 1234},
            "grid": {"current_price": 0.50, "mode": "BUY"},
            "optimizer": {"latest_decision": "CHARGE", "daily_savings_pln": 10.5}
        }
        
        routing_key = f"nodes.{NODE_ID}.telemetry"
        channel.basic_publish(
            exchange='telemetry',
            routing_key=routing_key,
            body=json.dumps(payload),
            properties=pika.BasicProperties(content_type='application/json')
        )
        print(f"📤 Published telemetry to {routing_key}")
        connection.close()

        # 3. Verify in API (Wait for worker to process)
        print("⏳ Waiting 5s for processing...")
        time.sleep(5)
        
        token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get node status
        resp = requests.get(f"{API_URL}/nodes", headers=headers)
        self.assertEqual(resp.status_code, 200)
        
        found = False
        for node in resp.json():
            if node["hardware_id"] == NODE_ID:
                found = True
                print(f"✅ Node Status: Online={node['is_online']}, Last Seen={node['last_seen']}")
                self.assertTrue(node['is_online'], "Node should be online")
                # Clean up if possible, or just leave it
                break
        
        self.assertTrue(found, "Test node not found in API")

if __name__ == "__main__":
    unittest.main()
