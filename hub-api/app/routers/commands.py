from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json
from ..database import get_db
from ..models import Node, User, UserRole, CommandAudit, CommandStatus
from ..schemas import CommandRequest, CommandAuditResponse
from ..mqtt import mqtt_manager
from .auth import get_current_user
from uuid import UUID

router = APIRouter(prefix="/nodes/{node_id}/command", tags=["commands"])

@router.post("/", response_model=CommandAuditResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_command(
    node_id: UUID,
    cmd_in: CommandRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Triggers a remote command to an edge node via MQTT.
    """
    # 1. Verify Node and Ownership
    result = await db.execute(select(Node).where(Node.id == node_id))
    node = result.scalars().first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    if current_user.role != UserRole.admin and node.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to control this node")

    # 2. Create Audit Entry
    audit = CommandAudit(
        node_id=node.id,
        user_id=current_user.id,
        command=cmd_in.command,
        payload=cmd_in.payload,
        status=CommandStatus.pending
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    # 3. Publish to MQTT
    topic = f"nodes/{node.hardware_id}/commands"
    payload = {
        "command_id": str(audit.id),
        "command": cmd_in.command,
        "payload": cmd_in.payload
    }
    
    try:
        await mqtt_manager.publish(topic, json.dumps(payload))
        audit.status = CommandStatus.sent
        await db.commit()
    except Exception as e:
        print(f"❌ Failed to publish command: {e}")
        audit.status = CommandStatus.failed
        await db.commit()
        raise HTTPException(status_code=500, detail="Failed to transmit command to broker")

    return audit
