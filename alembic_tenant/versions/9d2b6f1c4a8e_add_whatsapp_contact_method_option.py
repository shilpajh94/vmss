"""add `whatsapp` to the Preferred Contact Method field's options

Revision ID: 9d2b6f1c4a8e
Revises: e5f7a9b1c3d4
Create Date: 2026-10-13 00:00:00.000000

Data-only migration (no schema change). `preferredContactMethod` now accepts
`whatsapp` (integrate-fast2sms-dlt-sms) and `form_builder/defaults.py` seeds
the locked `preferred_contact_method` field with `email`, `sms`, `whatsapp`.
`seed_default_form_config` only seeds a tenant with no steps, and a published
scope serves its frozen snapshot, so a tenant seeded earlier would keep
offering only `email`/`sms`; being locked, an admin can't add the option.

Two stores hold the field per tenant: the live draft (`form_fields`) and the
published `form_config_versions.snapshot`. Both get `whatsapp` appended,
after the existing options. Idempotent: a field that already lists it is
left alone. The field is matched by `key`, since ids differ per tenant.

Operators must flush this tenant's `vmss:{tenant_id}:form-builder:effective:*`
Redis keys (or wait out the cache TTL) after running this: the effective
form is served from a cached copy until then.

No `downgrade()` data-reversal: removing the option could strand records
already created with `whatsapp`.
"""

import logging
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d2b6f1c4a8e"
down_revision: str | Sequence[str] | None = "e5f7a9b1c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.add_whatsapp_contact_method_option")

_FIELD_KEY = "preferred_contact_method"
_OPTION = "whatsapp"


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()
    conn = op.get_bind()

    drafts = conn.execute(
        text(
            f"""
            UPDATE {schema}.form_fields
            SET options = COALESCE(options, '[]'::jsonb) || to_jsonb(CAST(:option AS text))
            WHERE key = :key
              AND deleted_at IS NULL
              AND NOT COALESCE(options, '[]'::jsonb) ? :option
            """
        ),
        {"key": _FIELD_KEY, "option": _OPTION},
    )
    logger.info(
        "add_whatsapp_contact_method_option: updated %d draft form_fields row(s) in schema '%s'",
        drafts.rowcount,
        schema,
    )

    updated_versions = 0
    for row in conn.execute(text(f"SELECT id, snapshot FROM {schema}.form_config_versions")):
        snapshot: list[dict[str, Any]] = row.snapshot
        changed = False
        for step in snapshot:
            for field in step.get("fields", []):
                if field.get("key") != _FIELD_KEY:
                    continue
                options = field.get("options") or []
                if _OPTION not in options:
                    field["options"] = [*options, _OPTION]
                    changed = True
        if changed:
            conn.execute(
                text(
                    f"UPDATE {schema}.form_config_versions SET snapshot = :snapshot WHERE id = :id"
                ).bindparams(sa.bindparam("snapshot", type_=JSONB)),
                {"id": row.id, "snapshot": snapshot},
            )
            updated_versions += 1
    logger.info(
        "add_whatsapp_contact_method_option: rewrote %d published form_config_versions "
        "snapshot(s) in schema '%s'",
        updated_versions,
        schema,
    )


def downgrade() -> None:
    """No-op — see module docstring."""
