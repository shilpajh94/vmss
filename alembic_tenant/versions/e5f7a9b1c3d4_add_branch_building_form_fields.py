"""add system branch/building fields to every Visit Details form

Revision ID: e5f7a9b1c3d4
Revises: bd6dced25c1d
Create Date: 2026-10-06 00:00:00.000000

The effective form now carries locked `branch` ("Location") and `building`
dropdown fields on the `visit_details` step so clients can render them from
the API (`form_builder/defaults.py`). Fresh scopes get them from the seed
defaults; this backfills scopes seeded earlier: the draft `form_fields`
rows and the published `form_config_versions` snapshots.

Idempotent: a step or snapshot that already has a `branch` field is left
alone. Both fields are placed first on the step. Downgrade is a no-op —
removing them would orphan any form published since.
"""

import uuid
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f7a9b1c3d4"
down_revision: str | Sequence[str] | None = "bd6dced25c1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (key, label, is_required, help_text) — copied rather than imported so the
# migration stays fixed even if the app defaults move on.
_FIELDS: list[tuple[str, str, bool, str]] = [
    ("branch", "Location", True, "Populated from your Branches list."),
    ("building", "Building", False, "Populated from the selected branch's Buildings list."),
]


def _target_schema() -> str:
    return op.get_context().version_table_schema


def _backfill_rows(conn: sa.Connection, schema: str) -> dict[str, dict[str, str]]:
    """Returns {step_id: {field_key: field_id}} for every visit_details step."""
    steps = conn.execute(
        text(f"SELECT id FROM {schema}.form_steps WHERE key = 'visit_details'")
    ).fetchall()
    ids: dict[str, dict[str, str]] = {}
    for step in steps:
        existing = {
            r.key: str(r.id)
            for r in conn.execute(
                text(
                    f"SELECT id, key FROM {schema}.form_fields "
                    "WHERE step_id = :step_id AND key IN ('branch', 'building')"
                ),
                {"step_id": step.id},
            )
        }
        if "branch" not in existing:
            conn.execute(
                text(
                    f"UPDATE {schema}.form_fields SET order_index = order_index + 2 "
                    "WHERE step_id = :step_id"
                ),
                {"step_id": step.id},
            )
            for order, (key, label, required, help_text) in enumerate(_FIELDS):
                field_id = uuid.uuid4()
                conn.execute(
                    text(
                        f"INSERT INTO {schema}.form_fields (id, step_id, key, label, help_text, "
                        "field_type, is_system, is_locked, is_active, is_required, width, "
                        "hide_label, order_index) VALUES (:id, :step_id, :key, :label, "
                        ":help_text, 'dropdown_select', true, true, true, :required, 'full', "
                        "false, :order)"
                    ),
                    {
                        "id": field_id,
                        "step_id": step.id,
                        "key": key,
                        "label": label,
                        "help_text": help_text,
                        "required": required,
                        "order": order,
                    },
                )
                existing[key] = str(field_id)
        ids[str(step.id)] = existing
    return ids


def _patch_step(step: dict[str, Any], row_ids: dict[str, dict[str, str]]) -> bool:
    if step.get("key") != "visit_details":
        return False
    fields = step.get("fields", [])
    if any(f.get("key") == "branch" for f in fields):
        return False
    known = row_ids.get(step.get("id"), {})
    for f in fields:
        f["orderIndex"] = f.get("orderIndex", 0) + 2
    new_fields = [
        {
            "id": known.get(key, str(uuid.uuid4())),
            "stepId": step.get("id"),
            "groupId": None,
            "key": key,
            "label": label,
            "placeholder": None,
            "helpText": help_text,
            "fieldType": "dropdown_select",
            "isSystem": True,
            "isLocked": True,
            "isActive": True,
            "isRequired": required,
            "options": None,
            "validationRules": None,
            "visibilityCondition": None,
            "width": "full",
            "hideLabel": False,
            "orderIndex": order,
        }
        for order, (key, label, required, help_text) in enumerate(_FIELDS)
    ]
    step["fields"] = new_fields + fields
    return True


def upgrade() -> None:
    schema = _target_schema()
    conn = op.get_bind()
    row_ids = _backfill_rows(conn, schema)

    for row in conn.execute(text(f"SELECT id, snapshot FROM {schema}.form_config_versions")):
        snapshot: list[dict[str, Any]] = row.snapshot
        changed = False
        for step in snapshot:
            changed = _patch_step(step, row_ids) or changed
        if changed:
            conn.execute(
                text(
                    f"UPDATE {schema}.form_config_versions SET snapshot = :snapshot WHERE id = :id"
                ).bindparams(sa.bindparam("snapshot", type_=JSONB)),
                {"id": row.id, "snapshot": snapshot},
            )


def downgrade() -> None:
    """No-op — see module docstring."""
