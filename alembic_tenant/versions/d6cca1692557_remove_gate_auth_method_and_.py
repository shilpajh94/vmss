"""org structure: remove security gate auth_method and connectivity_status

Revision ID: d6cca1692557
Revises: a05c36d976c4
Create Date: 2026-08-27 00:00:00.000000

`SecurityGate.auth_method` and `SecurityGate.connectivity_status` (added by
524da546af26_desk_gate_tri_state_status.py) are no longer wanted on the gate
model — see
openspec/changes/update-employee-list-and-gate-crud/proposal.md. Confirmed
unused outside `org_structure/` before this drop (design.md's "Gate field
removal" decision), so this is a plain column drop, not a deprecate-in-place.
`SecurityGate.high_security` and `gate_type` are unaffected.

Both `op.drop_column` calls pass `schema=` explicitly per
524da546af26's documented landmine — `op.add_column`/`op.drop_column` do not
honor `schema_translate_map` the way `op.create_table` does.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6cca1692557"
down_revision: str | None = "a05c36d976c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    op.drop_column("security_gates", "auth_method", schema=schema)
    op.drop_column("security_gates", "connectivity_status", schema=schema)


def downgrade() -> None:
    schema = _target_schema()
    bind = op.get_bind()

    op.add_column(
        "security_gates",
        sa.Column("connectivity_status", sa.String(length=20), nullable=True),
        schema=schema,
    )
    bind.execute(sa.text(f"UPDATE \"{schema}\".security_gates SET connectivity_status = 'online'"))
    op.alter_column("security_gates", "connectivity_status", nullable=False, schema=schema)
    op.add_column(
        "security_gates",
        sa.Column("auth_method", sa.String(length=100), nullable=True),
        schema=schema,
    )
