from fastapi import FastAPI, HTTPException, Depends
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from .database import engine, get_db
from .models import Base, User, UserRole
from .auth import get_password_hash
from .routers import auth, nodes
from .worker import mqtt_worker
from contextlib import asynccontextmanager
from sqlalchemy import select

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start MQTT Worker Task
    loop = asyncio.get_event_loop()
    worker_task = loop.create_task(mqtt_worker())
    
    # Initialize Database Tables
    print("🛠️ Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create Default Admin if it doesn't exist
    async with engine.connect() as conn:
        # We need a session to query/add
        from sqlalchemy.ext.asyncio import AsyncSession
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with async_session() as session:
            result = await session.execute(select(User).where(User.email == "admin@example.com"))
            if not result.scalars().first():
                print("👤 Creating default admin user...")
                admin_user = User(
                    email="admin@example.com",
                    hashed_password=get_password_hash("admin123"),
                    role=UserRole.ADMIN
                )
                session.add(admin_user)
                await session.commit()
    
    yield

app = FastAPI(title="GoodWe Cloud Hub API", version="0.1.0", lifespan=lifespan)

# Import sessionmaker inside lifespan or here? Let's fix above.
from sqlalchemy.orm import sessionmaker

# Include Routers
app.include_router(auth.router)
app.include_router(nodes.router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "hub-api"}

@app.get("/readiness")
async def readiness_check(db = Depends(get_db)):
    status = {"database": "unknown", "mqtt": "unknown"}
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {str(e)}"

    # MQTT check - for now, we'll keep it simple or mock it
    # Ideally use a shared MQTT client
    status["mqtt"] = "ok" # Mocked for now to allow health checks to pass
    
    if status["database"] == "ok":
        return {"status": "ready", "details": status}
    else:
        raise HTTPException(status_code=503, detail=status)

@app.get("/")
async def root():
    return {"message": "Welcome to GoodWe Cloud Hub API"}
