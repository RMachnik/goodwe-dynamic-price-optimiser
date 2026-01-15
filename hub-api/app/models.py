from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, BigInteger, UUID, JSON
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime
import uuid
import enum

class Base(DeclarativeBase):
    pass

class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"

class CommandStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    acknowledged = "acknowledged"
    failed = "failed"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole, name="userrole"), default=UserRole.user)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    nodes = relationship("Node", back_populates="owner")
    commands = relationship("CommandAudit", back_populates="user")

class Node(Base):
    __tablename__ = "nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hardware_id = Column(String, unique=True, index=True, nullable=False)
    secret_hash = Column(String, nullable=False)
    name = Column(String, nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    config = Column(JSON, default={})
    last_seen = Column(DateTime, nullable=True)
    is_online = Column(Boolean, default=False)
    
    owner = relationship("User", back_populates="nodes")
    telemetry = relationship("Telemetry", back_populates="node")
    commands = relationship("CommandAudit", back_populates="node")

class Telemetry(Base):
    __tablename__ = "telemetry"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    data = Column(JSON, nullable=False)
    
    node = relationship("Node", back_populates="telemetry")

class CommandAudit(Base):
    __tablename__ = "command_audit"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    command = Column(String, nullable=False)
    payload = Column(JSON, default={})
    status = Column(Enum(CommandStatus, name="commandstatus"), default=CommandStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    node = relationship("Node", back_populates="commands")
    user = relationship("User", back_populates="commands")

class MarketPrice(Base):
    __tablename__ = "market_prices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True) # UTC
    price_pln_mwh = Column(Integer, nullable=False) # Store as integer (MWh) or Float
    source = Column(String, default="PSE")
