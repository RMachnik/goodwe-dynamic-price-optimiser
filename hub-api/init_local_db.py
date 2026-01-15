
import asyncio
from app.database import engine
from app.models import Base
from sqlalchemy import select
from app.models import User, UserRole
from app.auth import get_password_hash
from app.database import AsyncSessionLocal

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create admin
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        if not result.scalars().first():
            admin_user = User(
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.admin
            )
            session.add(admin_user)
            await session.commit()
            print("Admin created.")

if __name__ == "__main__":
    asyncio.run(init_db())
