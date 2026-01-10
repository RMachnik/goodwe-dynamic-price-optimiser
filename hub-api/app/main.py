from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from .database import engine, get_db
from .models import Base, User, UserRole
from .auth import get_password_hash
from .routers import auth, nodes, commands
from .worker import mqtt_worker
from .mqtt import mqtt_manager
from contextlib import asynccontextmanager
from sqlalchemy import select

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect MQTT Manager
    await mqtt_manager.connect()

    # Start MQTT Worker Task
    loop = asyncio.get_event_loop()
    worker_task = loop.create_task(mqtt_worker())
    
    # Create Default Admin if it doesn't exist
    from .database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).where(User.email == "admin@example.com"))
            if not result.scalars().first():
                print("👤 Creating default admin user...")
                admin_user = User(
                    email="admin@example.com",
                    hashed_password=get_password_hash("admin123"),
                    role=UserRole.admin
                )
                session.add(admin_user)
                await session.commit()
                print("✅ Default admin user created.")
        except Exception as e:
            print(f"⚠️ Error creating default admin: {e}")
            await session.rollback()
    
    yield
    await mqtt_manager.disconnect()

app = FastAPI(title="GoodWe Cloud Hub API", version="0.1.0", lifespan=lifespan)

# CORS Configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(nodes.router)
app.include_router(commands.router)

@app.get("/health")
async def health_check(db = Depends(get_db)):
    """Enhanced health check with connection status."""
    connections = {
        "database": "unknown",
        "mqtt": "unknown"
    }
    
    # Check database connection
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        connections["database"] = "connected"
    except Exception as e:
        connections["database"] = f"error: {str(e)[:50]}"
    
    # Check MQTT connection
    if mqtt_manager.client is not None:
        connections["mqtt"] = "connected"
    else:
        connections["mqtt"] = "disconnected"
    
    all_ok = connections["database"] == "connected"
    
    return {
        "status": "ok" if all_ok else "degraded",
        "service": "hub-api",
        "connections": connections
    }

@app.get("/readiness")
async def readiness_check(db = Depends(get_db)):
    status = {"database": "unknown", "mqtt": "unknown"}
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {str(e)}"

    # Real MQTT check
    if mqtt_manager.client is not None:
        status["mqtt"] = "ok"
    else:
        status["mqtt"] = "disconnected"
    
    if status["database"] == "ok":
        return {"status": "ready", "details": status}
    else:
        raise HTTPException(status_code=503, detail=status)

@app.get("/")
async def root():
    return {"message": "Welcome to GoodWe Cloud Hub API"}
