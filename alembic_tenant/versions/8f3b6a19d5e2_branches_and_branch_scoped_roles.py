"""org structure: branches; RBAC role grants scoped to a branch

Revision ID: 8f3b6a19d5e2
Revises: e0366161cbb8
Create Date: 2026-08-17 00:00:00.000000

Replaces the flat `user_roles` join table with `user_branch_roles`, which
adds a nullable `branch_id` — `NULL` means the grant applies to every branch
in the company (used for company-wide roles like Admin); a concrete id scopes
the grant to that one branch/location. See security-architecture.md §1 and
auth/models.py::User.has_permission.

Existing `user_roles` grants are carried forward as company-wide
(`branch_id=NULL`) rather than dropped: a grant made before branches existed
was implicitly "everywhere", which NULL now spells out explicitly. Data
migration goes through real `sa.Table()` objects on a throwaway `MetaData()`
(not `sa.table()`, the lightweight construct — it does NOT participate in
`schema_translate_map`, so it would silently resolve against whatever schema
is first on the connection's default `search_path` instead of the tenant
schema this run targets — verified against this project's own dev database,
which still carries a stray pre-schema-per-tenant `public.roles`/`public.users`
that a `sa.table()`-based migration would corrupt/misread silently. See
alembic_tenant/env.py and database-architecture.md §2.
"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8f3b6a19d5e2'
down_revision: str | None = 'e0366161cbb8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_data_metadata = sa.MetaData()

_user_roles_t = sa.Table(
    'user_roles',
    _data_metadata,
    sa.Column('user_id', sa.Uuid()),
    sa.Column('role_id', sa.Uuid()),
)
_user_branch_roles_t = sa.Table(
    'user_branch_roles',
    _data_metadata,
    sa.Column('id', sa.Uuid()),
    sa.Column('user_id', sa.Uuid()),
    sa.Column('role_id', sa.Uuid()),
    sa.Column('branch_id', sa.Uuid()),
)


def upgrade() -> None:
    op.create_table(
        'branches',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_branches_code'), 'branches', ['code'], unique=True)

    op.create_table(
        'user_branch_roles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('role_id', sa.Uuid(), nullable=False),
        sa.Column('branch_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', 'branch_id', name='uq_user_branch_role'),
    )
    op.create_index(op.f('ix_user_branch_roles_user_id'), 'user_branch_roles', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_branch_roles_branch_id'), 'user_branch_roles', ['branch_id'], unique=False)

    bind = op.get_bind()
    existing_grants = bind.execute(
        sa.select(_user_roles_t.c.user_id, _user_roles_t.c.role_id)
    ).fetchall()
    if existing_grants:
        bind.execute(
            _user_branch_roles_t.insert(),
            [
                {"id": uuid.uuid4(), "user_id": row.user_id, "role_id": row.role_id, "branch_id": None}
                for row in existing_grants
            ],
        )

    op.drop_table('user_roles')


def downgrade() -> None:
    op.create_table(
        'user_roles',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('role_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'role_id'),
    )

    bind = op.get_bind()
    # Only company-wide (branch_id IS NULL) grants survive a downgrade —
    # `user_roles` has no branch dimension to put a branch-scoped grant into.
    company_wide_grants = bind.execute(
        sa.select(_user_branch_roles_t.c.user_id, _user_branch_roles_t.c.role_id)
        .where(_user_branch_roles_t.c.branch_id.is_(None))
        .distinct()
    ).fetchall()
    if company_wide_grants:
        bind.execute(
            _user_roles_t.insert(),
            [{"user_id": row.user_id, "role_id": row.role_id} for row in company_wide_grants],
        )

    op.drop_index(op.f('ix_user_branch_roles_branch_id'), table_name='user_branch_roles')
    op.drop_index(op.f('ix_user_branch_roles_user_id'), table_name='user_branch_roles')
    op.drop_table('user_branch_roles')

    op.drop_index(op.f('ix_branches_code'), table_name='branches')
    op.drop_table('branches')
