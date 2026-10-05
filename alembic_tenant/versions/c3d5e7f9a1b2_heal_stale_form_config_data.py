"""heal stale form config data: removed field types and old snapshot keys

Revision ID: c3d5e7f9a1b2
Revises: b7c2e9a4d1f3
Create Date: 2026-09-30 00:00:00.000000

`update-form-field-type-catalog` removed `signature_pad`, `dynamic_table`
and `rich_text_block` from `FormFieldType` with no data migration, on the
belief that nothing stored used them. A field saved before that
(`terms_conditions`, `signature_pad`, in the dev tenant) made the admin
step list 500 and the published form unparseable. Snapshots published
before `hideLabel`, group `visibilityCondition` and group `fieldIds`
existed also lack those keys. This converts the removed types to the
nearest supported ones and backfills the keys
(heal-stale-form-config-data design.md Decisions 1–2).

The app also normalises snapshots on read (`form_builder/snapshot.py`);
this makes the stored data itself clean. The mapping and defaults are
copied here rather than imported, so the migration stays fixed even if
the app code moves on.

Idempotent: a second run finds nothing to change. Downgrade is a no-op —
restoring unsupported types would break the forms again.
"""

import logging
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d5e7f9a1b2"
down_revision: str | Sequence[str] | None = "b7c2e9a4d1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.heal_stale_form_config_data")

# removed type -> (replacement, clear options)
_REMAP: dict[str, tuple[str, bool]] = {
    "signature_pad": ("checkbox_single", True),
    "rich_text_block": ("static_text", False),
    "dynamic_table": ("textarea", True),
}
_FIELD_DEFAULTS: dict[str, Any] = {"hideLabel": False}
_GROUP_DEFAULTS: dict[str, Any] = {"visibilityCondition": None}


def _target_schema() -> str:
    return op.get_context().version_table_schema


def _heal_rows(conn: sa.Connection, schema: str) -> None:
    # Soft-deleted rows too, so an undelete can't bring a broken row back.
    rows = conn.execute(
        text(
            f"SELECT id, key, field_type FROM {schema}.form_fields WHERE field_type IN :types"
        ).bindparams(sa.bindparam("types", expanding=True)),
        {"types": list(_REMAP)},
    ).fetchall()
    for row in rows:
        new_type, clear_options = _REMAP[row.field_type]
        conn.execute(
            text(
                f"UPDATE {schema}.form_fields SET field_type = :new_type"
                + (", options = NULL" if clear_options else "")
                + " WHERE id = :id"
            ),
            {"new_type": new_type, "id": row.id},
        )
        logger.info(
            "heal_stale_form_config_data: form_fields %s (%s) %s -> %s in schema '%s'",
            row.id,
            row.key,
            row.field_type,
            new_type,
            schema,
        )


def _heal_step(step: dict[str, Any], *, schema: str, version_id: object) -> bool:
    changed = False
    for field in step.get("fields", []):
        old_type = field.get("fieldType")
        if old_type in _REMAP:
            new_type, clear_options = _REMAP[old_type]
            field["fieldType"] = new_type
            if clear_options:
                field["options"] = None
            changed = True
            logger.info(
                "heal_stale_form_config_data: snapshot %s field %s (%s) %s -> %s in schema '%s'",
                version_id,
                field.get("id"),
                field.get("key"),
                old_type,
                new_type,
                schema,
            )
        for key, default in _FIELD_DEFAULTS.items():
            if key not in field:
                field[key] = default
                changed = True
    id_by_key = {field.get("key"): field.get("id") for field in step.get("fields", [])}
    for group in step.get("groups", []):
        for key, default in _GROUP_DEFAULTS.items():
            if key not in group:
                group[key] = default
                changed = True
        if "fieldIds" not in group:
            group["fieldIds"] = [
                id_by_key[key] for key in group.get("fieldKeys", []) if key in id_by_key
            ]
            changed = True
    return changed


def upgrade() -> None:
    schema = _target_schema()
    conn = op.get_bind()
    _heal_rows(conn, schema)

    versions = conn.execute(
        text(f"SELECT id, snapshot FROM {schema}.form_config_versions")
    ).fetchall()
    rewritten = 0
    for row in versions:
        snapshot: list[dict[str, Any]] = row.snapshot
        changed = False
        for step in snapshot:
            changed = _heal_step(step, schema=schema, version_id=row.id) or changed
        if changed:
            conn.execute(
                text(
                    f"UPDATE {schema}.form_config_versions SET snapshot = :snapshot WHERE id = :id"
                ).bindparams(sa.bindparam("snapshot", type_=JSONB)),
                {"id": row.id, "snapshot": snapshot},
            )
            rewritten += 1
    logger.info(
        "heal_stale_form_config_data: rewrote %d form_config_versions snapshot(s) in schema '%s'",
        rewritten,
        schema,
    )


def downgrade() -> None:
    """No-op — see module docstring."""
