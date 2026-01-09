import pytest
import asyncio
import aiomqtt
import os
import time

MQTT_BROKER = "localhost"
MQTT_PORT = 1883

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mqtt_acl_isolation():
    """
    Verify that a node can ONLY access its own topics.
    """
    node_id = "mock-node-01"
    node_pass = "secret123"
    other_node_topic = "nodes/secret-node/telemetry"
    
    # 1. Connect as mock-node-01
    async with aiomqtt.Client(
        hostname=MQTT_BROKER, 
        port=MQTT_PORT,
        username=node_id,
        password=node_pass
    ) as client:
        print(f"✅ Connected as {node_id}")
        
        # 2. Try to subscribe to someone else's topic
        # Mosquitto 2.0+ with ACLs will silently ignore or deny
        try:
            await client.subscribe(other_node_topic)
            print(f"⚠️ Subscribed to {other_node_topic} (should be restricted by ACL)")
        except Exception as e:
            print(f"✅ Subscription denied as expected: {e}")
            return # Success if denied
            
        # 3. If subscription didn't raise, verify no messages arrive
        # We'll publish to that topic using the Hub account (which HAS access)
        # and see if mock-node-01 receives it.
        async with aiomqtt.Client(
            hostname=MQTT_BROKER, 
            port=MQTT_PORT,
            username="hub_api",
            password="hub_secret"
        ) as hub_client:
            await hub_client.publish(other_node_topic, payload="secret data")
            
        # Wait a bit to see if message arrives
        try:
            async with asyncio.timeout(2):
                async for message in client.messages:
                    if str(message.topic) == other_node_topic:
                        pytest.fail(f"❌ SECURITY BREACH: node {node_id} received data from {other_node_topic}")
        except asyncio.TimeoutError:
            print(f"✅ Isolation verified: No messages received from {other_node_topic}")

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mqtt_auth_failure():
    """
    Verify that connection without valid credentials fails.
    """
    try:
        async with aiomqtt.Client(
            hostname=MQTT_BROKER, 
            port=MQTT_PORT,
            username="invalid",
            password="wrong"
        ) as client:
            pytest.fail("❌ SECURITY BREACH: Connected with invalid credentials")
    except Exception as e:
        print(f"✅ Connection denied as expected: {e}")
