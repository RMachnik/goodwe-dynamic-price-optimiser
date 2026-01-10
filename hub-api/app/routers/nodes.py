from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from ..database import get_db
from ..models import Node, User, UserRole
from ..schemas import NodeCreate, NodeResponse, NodeUpdate, TelemetryResponse
from .auth import get_current_user, admin_required
from uuid import UUID

router = APIRouter(prefix="/nodes", tags=["nodes"])

@router.post("/", response_model=NodeResponse)
async def enroll_node(
    node_in: NodeCreate, 
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(admin_required)
):
    # Check if node already registered
    result = await db.execute(select(Node).where(Node.hardware_id == node_in.hardware_id))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Node already registered")
    
    # In a real scenario, we'd hash the secret
    from hashlib import sha256
    secret_hash = sha256(node_in.secret.encode()).hexdigest()
    
    new_node = Node(
        hardware_id=node_in.hardware_id,
        secret_hash=secret_hash,
        name=node_in.name,
        config=node_in.config
    )
    db.add(new_node)
    await db.commit()
    await db.refresh(new_node)
    return new_node

@router.get("/", response_model=List[NodeResponse])
async def list_nodes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == UserRole.admin:
        result = await db.execute(select(Node))
    else:
        result = await db.execute(select(Node).where(Node.owner_id == current_user.id))
    return result.scalars().all()

@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Node).where(Node.id == node_id))
    node = result.scalars().first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    if current_user.role != UserRole.admin and node.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this node")
    
    return node

@router.patch("/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: UUID,
    node_update: NodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Node).where(Node.id == node_id))
    node = result.scalars().first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    if current_user.role != UserRole.admin and node.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this node")
    
    if node_update.name is not None:
        node.name = node_update.name
    if node_update.config is not None:
        node.config = node_update.config
        # Future: Trigger MQTT config update here
        
    await db.commit()
    await db.refresh(node)
    return node

@router.get("/{node_id}/telemetry", response_model=List[TelemetryResponse])
async def get_node_telemetry(
    node_id: UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from ..models import Telemetry
    from sqlalchemy import desc
    
    # Check authorization
    result = await db.execute(select(Node).where(Node.id == node_id))
    node = result.scalars().first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    if current_user.role != UserRole.admin and node.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this node's telemetry")
    
    # Get telemetry
    result = await db.execute(
        select(Telemetry)
        .where(Telemetry.node_id == node_id)
        .order_by(desc(Telemetry.timestamp))
        .limit(limit)
    )
    return result.scalars().all()

