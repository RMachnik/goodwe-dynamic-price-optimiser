from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import secrets
import logging

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key-for-dev-only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# FastAPI dependency for getting current user
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(lambda: None)  # Placeholder, will be injected
):
    """
    Dependency function to extract and validate the current user from JWT token.
    Usage: current_user: User = Depends(get_current_user)
    """
    from .models import User
    from .database import get_db
    
    if db is None:
        async for session in get_db():
            db = session
            break
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception
        
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

async def _get_node_from_headers(db: AsyncSession, node_id: str, node_secret: str):
    """
    Internal helper to authenticate a Node via X-Node-ID and X-Node-Secret headers.
    Uses timing-attack-safe comparison via secrets.compare_digest.
    """
    from .models import Node
    from .database import get_db
    from hashlib import sha256

    if not node_id or not node_secret:
        return None

    if db is None:
        async for session in get_db():
            db = session
            break

    result = await db.execute(select(Node).where(Node.hardware_id == node_id))
    node = result.scalars().first()
    
    if node:
        provided_hash = sha256(node_secret.encode()).hexdigest()
        # Timing-attack safe comparison (Principal Engineer Fix)
        if secrets.compare_digest(provided_hash, node.secret_hash):
            return node
            
    return None

async def get_authenticated_entity(
    request: Request,
    node_id: Optional[str] = Header(None, alias="X-Node-ID"),
    node_secret: Optional[str] = Header(None, alias="X-Node-Secret"),
    db: AsyncSession = Depends(lambda: None)
) -> Union["User", "Node"]:
    """
    Unified dependency: Allows EITHER a User (JWT) OR a Node (Headers).
    Returns either a User object or a Node object.
    
    Authentication priority:
    1. Node credentials (X-Node-ID + X-Node-Secret headers)
    2. User JWT (Authorization: Bearer <token>)
    """
    from .models import User, Node
    from .database import get_db
    
    if db is None:
        async for session in get_db():
            db = session
            break
            
    # 1. Try Node Auth (X-Node-ID + X-Node-Secret)
    if node_id and node_secret:
        node = await _get_node_from_headers(db, node_id, node_secret)
        if node:
            logger.debug(f"Authenticated as Node: {node.hardware_id}")
            return node

    # 2. Try User Auth (JWT inside Authorization: Bearer <token>)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = decode_access_token(token)
        if payload:
            email = payload.get("sub")
            if email:
                result = await db.execute(select(User).where(User.email == email))
                user = result.scalars().first()
                if user:
                    logger.debug(f"Authenticated as User: {user.email}")
                    return user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide valid JWT token or Node credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
