"""invitations trigram search indexes

Revision ID: 14319832f01f
Revises: fe66e482f4c5
Create Date: 2026-10-22 09:56:23.200507

`GET /invitations?search=` matches `ILIKE '%term%'` on the primary contact's
name and the tracking id (`invitations/repository.py`), which no b-tree can
serve. GIN trigram indexes can (audit-and-harden-api-and-web design.md D9).

`pg_trgm` is created if missing, inside a savepoint. Where the database role
can't create extensions (some managed Postgres plans), the indexes are
skipped with a notice instead of failing the upgrade: search keeps working,
just unindexed. Re-run after an operator installs the extension.

`schema=`/qualified names are explicit: index DDL on a pre-existing table
ignores `schema_translate_map`.
"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14319832f01f"
down_revision: str | Sequence[str] | None = "fe66e482f4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = {
    "ix_invitations_primary_contact_full_name_trgm": "primary_contact_full_name",
    "ix_invitations_tracking_id_trgm": "tracking_id",
}
_log = logging.getLogger("alembic.runtime.migration")


def _trgm_available() -> bool:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")).scalar():
        return True
    savepoint = bind.begin_nested()
    try:
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    except sa.exc.DBAPIError:
        savepoint.rollback()
        return False
    savepoint.commit()
    return True


def upgrade() -> None:
    schema = op.get_context().version_table_schema
    if not _trgm_available():
        _log.warning(
            "pg_trgm is unavailable; skipped invitation search indexes in %s. "
            "Install the extension and re-run this migration to add them.",
            schema,
        )
        return
    trgm_schema = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT n.nspname FROM pg_extension e "
                "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'pg_trgm'"
            )
        )
        .scalar_one()
    )
    for name, column in _INDEXES.items():
        op.execute(
            f'CREATE INDEX IF NOT EXISTS "{name}" ON "{schema}".invitations '
            f'USING gin ({column} "{trgm_schema}".gin_trgm_ops)'
        )


def downgrade() -> None:
    schema = op.get_context().version_table_schema
    for name in _INDEXES:
        op.execute(f'DROP INDEX IF EXISTS "{schema}"."{name}"')
