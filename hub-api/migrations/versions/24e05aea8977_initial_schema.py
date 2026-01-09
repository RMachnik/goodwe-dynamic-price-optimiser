"""Initial schema

Revision ID: 24e05aea8977
Revises: 
Create Date: 2026-01-09 22:31:25.449960

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '24e05aea8977'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('role', sa.Enum('admin', 'user', name='userrole'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Nodes table
    op.create_table(
        'nodes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('hardware_id', sa.String(), nullable=False),
        sa.Column('secret_hash', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('owner_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('config', JSONB(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('is_online', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_nodes_hardware_id'), 'nodes', ['hardware_id'], unique=True)

    # Telemetry table
    op.create_table(
        'telemetry',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('node_id', sa.UUID(), sa.ForeignKey('nodes.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('data', JSONB(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_telemetry_timestamp'), 'telemetry', ['timestamp'], unique=False)

    # Command audit table
    op.create_table(
        'command_audit',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('node_id', sa.UUID(), sa.ForeignKey('nodes.id'), nullable=False),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('command', sa.String(), nullable=False),
        sa.Column('payload', JSONB(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'sent', 'acknowledged', 'failed', name='commandstatus'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('command_audit')
    op.drop_table('telemetry')
    op.drop_table('nodes')
    op.drop_table('users')
    # Types usually need to be dropped manually if they were created implicitly but let's see
    op.execute("DROP TYPE commandstatus")
    op.execute("DROP TYPE userrole")
