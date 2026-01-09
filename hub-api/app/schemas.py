from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from .models import UserRole, CommandStatus

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.USER

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Node Schemas
class NodeBase(BaseModel):
    hardware_id: str
    name: Optional[str] = None
    config: dict = {}

class NodeCreate(NodeBase):
    secret: str

class NodeUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None

class NodeResponse(NodeBase):
    id: UUID
    owner_id: Optional[UUID]
    last_seen: Optional[datetime]
    is_online: bool

    class Config:
        from_attributes = True

# Telemetry Schemas
class TelemetryResponse(BaseModel):
    timestamp: datetime
    data: dict

    class Config:
        from_attributes = True
