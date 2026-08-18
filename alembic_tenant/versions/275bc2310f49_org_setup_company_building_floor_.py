"""org setup: company, building, floor, department, reception desk,
security gate, and employee-directory fields on users

Revision ID: 275bc2310f49
Revises: 8f3b6a19d5e2
Create Date: 2026-08-17 00:00:00.000000

Adds the rest of the org chart under `Branch`: Branch -> Building -> Floor ->
Department (project decision — see docs/features/org_structure.md), plus
`ReceptionDesk`/`SecurityGate` (also floor/branch-scoped) and `Company` (this
tenant's own business profile, a singleton enforced in `service.py`, not
here). `users` gains the optional employee-directory columns
(`employee_code`, `designation`, `phone_number`, `department_id`) that
`auth/service.py::sync_employee_directory` populates.

Hand-written, not `alembic revision --autogenerate`: this environment's
`include_schemas=True` (needed so the tenant-schema comparison can see the
`global` schema for the existing `role_permissions -> global.permissions`
FK) makes autogenerate try to reflect the global-schema `permissions` table
under this run's `schema_translate_map`-bound connection, which raises
`NoSuchTableError` — a pre-existing limitation of this setup, not something
new here. Every migration in this tree so far is hand-written for the same
reason (see e0366161cbb8/8f3b6a19d5e2).

The `users` alterations below pass `schema=_target_schema()` explicitly —
verified against a real run that `op.add_column`/`op.drop_column` do NOT
pick up the connection's `schema_translate_map` the way `op.create_table`/
`op.create_index` do: without it, `ADD COLUMN` silently landed on the stray
pre-schema-per-tenant `public.users` table this dev database still carries
(see 8f3b6a19d5e2's docstring for the same landmine) instead of the target
tenant schema, and the very next `CREATE INDEX` (which *does* resolve via
the translate map) then failed with "column does not exist". Every other
statement here targets a table this same migration just created, so the
translate map alone is enough for those.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '275bc2310f49'
down_revision: str | None = '8f3b6a19d5e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    op.create_table(
        'companies',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('legal_name', sa.String(length=255), nullable=False),
        sa.Column('registration_number', sa.String(length=100), nullable=True),
        sa.Column('tax_id', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('registration_number'),
    )

    op.create_table(
        'buildings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('branch_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('branch_id', 'code', name='uq_building_branch_code'),
    )
    op.create_index(op.f('ix_buildings_branch_id'), 'buildings', ['branch_id'], unique=False)

    op.create_table(
        'floors',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('building_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('floor_number', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['building_id'], ['buildings.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('building_id', 'floor_number', name='uq_floor_building_number'),
    )
    op.create_index(op.f('ix_floors_building_id'), 'floors', ['building_id'], unique=False)

    op.create_table(
        'departments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('floor_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['floor_id'], ['floors.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('floor_id', 'code', name='uq_department_floor_code'),
    )
    op.create_index(op.f('ix_departments_floor_id'), 'departments', ['floor_id'], unique=False)

    op.create_table(
        'reception_desks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('floor_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['floor_id'], ['floors.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('floor_id', 'code', name='uq_desk_floor_code'),
    )
    op.create_index(op.f('ix_reception_desks_floor_id'), 'reception_desks', ['floor_id'], unique=False)

    op.create_table(
        'security_gates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('branch_id', sa.Uuid(), nullable=False),
        sa.Column('building_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('gate_type', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['building_id'], ['buildings.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('branch_id', 'code', name='uq_gate_branch_code'),
    )
    op.create_index(op.f('ix_security_gates_branch_id'), 'security_gates', ['branch_id'], unique=False)
    op.create_index(op.f('ix_security_gates_building_id'), 'security_gates', ['building_id'], unique=False)

    schema = _target_schema()
    op.add_column(
        'users', sa.Column('employee_code', sa.String(length=50), nullable=True), schema=schema
    )
    op.add_column(
        'users', sa.Column('designation', sa.String(length=100), nullable=True), schema=schema
    )
    op.add_column(
        'users', sa.Column('phone_number', sa.String(length=50), nullable=True), schema=schema
    )
    op.add_column(
        'users', sa.Column('department_id', sa.Uuid(), nullable=True), schema=schema
    )
    op.create_index(
        op.f('ix_users_employee_code'), 'users', ['employee_code'], unique=True, schema=schema
    )
    op.create_index(
        op.f('ix_users_department_id'), 'users', ['department_id'], unique=False, schema=schema
    )
    op.create_foreign_key(
        'fk_users_department_id',
        'users',
        'departments',
        ['department_id'],
        ['id'],
        source_schema=schema,
        referent_schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_constraint('fk_users_department_id', 'users', type_='foreignkey', schema=schema)
    op.drop_index(op.f('ix_users_department_id'), table_name='users', schema=schema)
    op.drop_index(op.f('ix_users_employee_code'), table_name='users', schema=schema)
    op.drop_column('users', 'department_id', schema=schema)
    op.drop_column('users', 'phone_number', schema=schema)
    op.drop_column('users', 'designation', schema=schema)
    op.drop_column('users', 'employee_code', schema=schema)

    op.drop_index(op.f('ix_security_gates_building_id'), table_name='security_gates')
    op.drop_index(op.f('ix_security_gates_branch_id'), table_name='security_gates')
    op.drop_table('security_gates')

    op.drop_index(op.f('ix_reception_desks_floor_id'), table_name='reception_desks')
    op.drop_table('reception_desks')

    op.drop_index(op.f('ix_departments_floor_id'), table_name='departments')
    op.drop_table('departments')

    op.drop_index(op.f('ix_floors_building_id'), table_name='floors')
    op.drop_table('floors')

    op.drop_index(op.f('ix_buildings_branch_id'), table_name='buildings')
    op.drop_table('buildings')

    op.drop_table('companies')
