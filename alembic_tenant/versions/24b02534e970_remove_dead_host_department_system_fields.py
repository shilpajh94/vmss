"""remove dead host/department_to_visit system fields from visit_details

Revision ID: 24b02534e970
Revises: d4b6f8a1c3e7
Create Date: 2026-09-28 00:00:00.000000

Data-only migration (no schema change). `host` and `department_to_visit`
were seeded, locked (`is_locked=True`) Visit Details system fields
(`form_builder/defaults.py`) that the visitor-facing wizard has never
actually collected: `host_name_or_email` is always discarded by
`invitations/service.py::_resolve_visit_detail_ids`
(role-based-invitation-workflow), and `department_to_visit` is always free
text or resolved from the `departmentId` catalog, never gated by a Form
Builder option list (see the matching change to `invitations/service.py`'s
`retypeable_field_values`). Being locked, neither could be removed through
the ordinary Form Builder admin API either
(`form_builder/service.py::delete_field` rejects a locked field with 422) —
the frontend had worked around this with a hardcoded field-label hide list
in its Form Builder step editor instead of a real fix. Both fields remain
fully real, independently populated columns on `Invitation`, set by
reception/staff through their own dedicated UI — this migration only
removes their dead, ignored representation as Visit Details form-builder
fields.

Two stores hold this field per tenant: the live draft (`form_fields`,
soft-deleted here — mirrors `form_builder/service.py::delete_field`'s own
soft delete) and, for any branch/tenant-default scope that has ever been
published, the frozen `form_config_versions.snapshot` JSONB
`resolve_effective_form` actually serves from once a scope has published at
least once (a published scope never falls back to the live draft rows).
Both are rewritten here, or an already-published tenant would keep serving
`host`/`department_to_visit` from its snapshot regardless of the draft-side
change.

Operators must flush this tenant's `vmss:{tenant_id}:form-builder:effective:*`
Redis keys (or wait out `resolve_effective_form`'s `_CACHE_TTL_SECONDS`)
after running this migration — `resolve_effective_form` serves a cached
copy of the pre-migration snapshot until that cache entry expires or is
invalidated by the tenant's next publish.

No `downgrade()` data-reversal is provided: the removed field rows/snapshot
entries carried real ids and orderIndex positions that aren't reconstructed
here, and there are no answers referencing them to preserve either way — an
operator rolling back would need a database backup taken before this
migration ran, not this file.
"""

import logging
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "24b02534e970"
down_revision: str | None = "d4b6f8a1c3e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.remove_dead_host_department_system_fields")

_DEAD_FIELD_KEYS = ("host", "department_to_visit")


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    conn = op.get_bind()

    deleted = conn.execute(
        text(
            f"""
            UPDATE {schema}.form_fields ff
            SET deleted_at = now()
            FROM {schema}.form_steps fs
            WHERE ff.step_id = fs.id
              AND fs.key = 'visit_details'
              AND ff.key IN :keys
              AND ff.deleted_at IS NULL
            """
        ).bindparams(sa.bindparam("keys", expanding=True)),
        {"keys": list(_DEAD_FIELD_KEYS)},
    )
    logger.info(
        "remove_dead_host_department_system_fields: soft-deleted %d draft "
        "form_fields row(s) in schema '%s'",
        deleted.rowcount,
        schema,
    )

    versions = conn.execute(
        text(f"SELECT id, snapshot FROM {schema}.form_config_versions")
    ).fetchall()
    updated_versions = 0
    for row in versions:
        snapshot: list[dict[str, Any]] = row.snapshot
        changed = False
        for step in snapshot:
            if step.get("key") != "visit_details":
                continue
            fields = step.get("fields", [])
            new_fields = [f for f in fields if f.get("key") not in _DEAD_FIELD_KEYS]
            if len(new_fields) != len(fields):
                step["fields"] = new_fields
                changed = True
        if changed:
            conn.execute(
                text(
                    f"UPDATE {schema}.form_config_versions SET snapshot = :snapshot WHERE id = :id"
                ).bindparams(sa.bindparam("snapshot", type_=sa.dialects.postgresql.JSONB)),
                {"id": row.id, "snapshot": snapshot},
            )
            updated_versions += 1

    logger.info(
        "remove_dead_host_department_system_fields: rewrote %d published "
        "form_config_versions snapshot(s) in schema '%s'",
        updated_versions,
        schema,
    )


def downgrade() -> None:
    """No-op — see module docstring."""
