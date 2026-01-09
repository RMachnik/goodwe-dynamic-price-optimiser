from fastapi import FastAPI, HTTPException
import os
import aiomqtt
import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from contextlib import asynccontextmanager

# In-memory storage for E2E verification before DB implementation
latest_telemetry = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background MQTT listener
    loop = asyncio.get_event_loop()
    task = loop.create_task(mqtt_listener())
    yield
    task.cancel()

app = FastAPI(title="GoodWe Cloud Hub API", version="0.1.0", lifespan=lifespan)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@db:5432/goodwe_hub")
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

async def mqtt_listener():
    """Background task to listen for telemetry and store in memory for E2E testing."""
    print(f"📡 Starting Hub MQTT Listener (connecting to {MQTT_BROKER})...")
    while True:
        try:
            async with aiomqtt.Client(hostname=MQTT_BROKER, port=MQTT_PORT) as client:
                await client.subscribe("nodes/+/telemetry")
                async for message in client.messages:
                    print(f"📥 Received telemetry on {message.topic}")
                    try:
                        data = json.loads(message.payload.decode())
                        node_id = data.get("node_id", "unknown")
                        latest_telemetry[node_id] = data
                    except Exception as e:
                        print(f"⚠️ Failed to parse message: {e}")
        except Exception as e:
            print(f"❌ Hub MQTT Error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "hub-api"}

@app.get("/readiness")
async def readiness_check():
    status = {"database": "unknown", "mqtt": "unknown"}
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {str(e)}"

    try:
        async with aiomqtt.Client(hostname=MQTT_BROKER, port=MQTT_PORT, timeout=2) as client:
            status["mqtt"] = "ok"
    except Exception as e:
        status["mqtt"] = f"error: {str(e)}"
    
    if status["database"] == "ok" and status["mqtt"] == "ok":
        return {"status": "ready", "details": status}
    else:
        raise HTTPException(status_code=503, detail=status)

@app.get("/telemetry/{node_id}")
async def get_latest_telemetry(node_id: str):
    """Endpoint for E2E verification of telemetry flow."""
    if node_id not in latest_telemetry:
        raise HTTPException(status_code=404, detail="No telemetry received for this node yet")
    return latest_telemetry[node_id]

@app.get("/")
async def root():
    return {"message": "Welcome to GoodWe Cloud Hub API"}
