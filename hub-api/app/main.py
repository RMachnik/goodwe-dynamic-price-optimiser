from fastapi import FastAPI, HTTPException
import os
import aiomqtt
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

app = FastAPI(title="GoodWe Cloud Hub API", version="0.1.0")

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@db:5432/goodwe_hub")
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "hub-api"}

@app.get("/readiness")
async def readiness_check():
    """
    Checks connectivity to dependent services (DB, MQTT).
    """
    status = {"database": "unknown", "mqtt": "unknown"}
    
    # 1. Check Database
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {str(e)}"

    # 2. Check MQTT
    try:
        # Check if we can connect to the broker
        async with aiomqtt.Client(hostname=MQTT_BROKER, port=MQTT_PORT, timeout=2) as client:
            status["mqtt"] = "ok"
    except Exception as e:
        status["mqtt"] = f"error: {str(e)}"
    
    # Determine overall status
    if status["database"] == "ok" and status["mqtt"] == "ok":
        return {"status": "ready", "details": status}
    else:
        raise HTTPException(status_code=503, detail=status)

@app.get("/")
async def root():
    return {"message": "Welcome to GoodWe Cloud Hub API"}
