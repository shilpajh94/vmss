"""audit_logs entity and actor indexes

Revision ID: fe66e482f4c5
Revises: a7c3e1d9b5f2
Create Date: 2026-10-22 09:55:22.674451

`audit_trail/repository.py` filters the trail by entity ("history of entity
X", newest first) and by actor, but only `action` and `created_at` were
indexed (audit-and-harden-api-and-web design.md D9). A plain ascending
composite serves `ORDER BY created_at DESC` too: Postgres scans it backwards.

`schema=` is passed explicitly: `create_index` on a pre-existing table
ignores `schema_translate_map`.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fe66e482f4c5"
down_revision: str | Sequence[str] | None = "a7c3e1d9b5f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_INDEX = "ix_audit_logs_entity_type_entity_id_created_at"
_ACTOR_INDEX = "ix_audit_logs_actor_user_id"


def upgrade() -> None:
    schema = op.get_context().version_table_schema
    op.create_index(
        _ENTITY_INDEX, "audit_logs", ["entity_type", "entity_id", "created_at"], schema=schema
    )
    op.create_index(_ACTOR_INDEX, "audit_logs", ["actor_user_id"], schema=schema)


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    op.drop_index(_ACTOR_INDEX, table_name="audit_logs", schema=schema)
    op.drop_index(_ENTITY_INDEX, table_name="audit_logs", schema=schema)
