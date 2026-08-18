"""initial global schema: tenants, superadmins, permissions, auth index

Revision ID: 02dfcb7b1ddc
Revises:
Create Date: 2026-08-17 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '02dfcb7b1ddc'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "global"


def upgrade() -> None:
    op.create_table(
        'tenants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('schema_name', sa.String(length=63), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index(op.f('ix_global_tenants_slug'), 'tenants', ['slug'], unique=True, schema=SCHEMA)
    op.create_index(
        op.f('ix_global_tenants_schema_name'), 'tenants', ['schema_name'], unique=True, schema=SCHEMA
    )

    op.create_table(
        'superadmins',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index(op.f('ix_global_superadmins_email'), 'superadmins', ['email'], unique=True, schema=SCHEMA)

    op.create_table(
        'permissions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index(op.f('ix_global_permissions_code'), 'permissions', ['code'], unique=True, schema=SCHEMA)

    op.create_table(
        'tenant_user_index',
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['global.tenants.id']),
        sa.PrimaryKeyConstraint('email'),
        schema=SCHEMA,
    )
    op.create_index(
        op.f('ix_global_tenant_user_index_tenant_id'), 'tenant_user_index', ['tenant_id'], unique=False, schema=SCHEMA
    )

    op.create_table(
        'tenant_schema_versions',
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('revision', sa.String(length=32), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['global.tenants.id']),
        sa.PrimaryKeyConstraint('tenant_id'),
        schema=SCHEMA,
    )

    op.create_table(
        'platform_audit_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actor_superadmin_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_tenant_id', sa.Uuid(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_superadmin_id'], ['global.superadmins.id']),
        sa.ForeignKeyConstraint(['target_tenant_id'], ['global.tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index(
        op.f('ix_global_platform_audit_events_action'), 'platform_audit_events', ['action'],
        unique=False, schema=SCHEMA,
    )
    op.create_index(
        op.f('ix_global_platform_audit_events_created_at'), 'platform_audit_events', ['created_at'],
        unique=False, schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table('platform_audit_events', schema=SCHEMA)
    op.drop_table('tenant_schema_versions', schema=SCHEMA)
    op.drop_index(op.f('ix_global_tenant_user_index_tenant_id'), table_name='tenant_user_index', schema=SCHEMA)
    op.drop_table('tenant_user_index', schema=SCHEMA)
    op.drop_index(op.f('ix_global_permissions_code'), table_name='permissions', schema=SCHEMA)
    op.drop_table('permissions', schema=SCHEMA)
    op.drop_index(op.f('ix_global_superadmins_email'), table_name='superadmins', schema=SCHEMA)
    op.drop_table('superadmins', schema=SCHEMA)
    op.drop_index(op.f('ix_global_tenants_schema_name'), table_name='tenants', schema=SCHEMA)
    op.drop_index(op.f('ix_global_tenants_slug'), table_name='tenants', schema=SCHEMA)
    op.drop_table('tenants', schema=SCHEMA)
