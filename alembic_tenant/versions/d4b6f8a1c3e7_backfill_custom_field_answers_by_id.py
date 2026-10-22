"""backfill custom field/consent/group answers keyed by field id

Revision ID: d4b6f8a1c3e7
Revises: 6154ee8e944b
Create Date: 2026-09-25 00:00:00.000000

Data-only migration (no schema change) for
`restructure-walkin-payload-by-field-id`. Before this change,
`invitations.custom_field_values`/`primary_contact_custom_field_values`/
`consents`, `invitation_visitors.custom_field_values`,
`invitation_vehicles.custom_field_values`, and each entry of
`invitations.group_field_values` were JSONB maps keyed by the admin-authored
`FormField`/`FormFieldGroup`'s `key` (a string). The application now reads
and writes these maps keyed by that field/group's `id` (a UUID) instead —
see design.md Decision 3.2. This migration best-effort rewrites every
existing row's stored keys from `key` to `id`, using each row's own
`branch_id` to resolve the *currently live* `form_fields`/`form_field_groups`
scoped to that branch (branch-specific rows, falling back to the
tenant-wide default scope — `branch_id IS NULL` — for any key not covered
by the branch's own fields, mirroring `form_builder`'s branch-with-
tenant-default-fallback scoping model).

A stored key with no matching *current* live field/group (the field was
deleted or renamed since the row was submitted) is left under its original
key, untouched — there is no live definition left to correctly re-key it
against, and dropping historical data silently would be worse than leaving
it queryable under its old key (design.md Decision 4). The count of such
orphaned keys is logged per tenant/table so an operator can investigate
rather than the gap passing unnoticed.

This is a data migration, not a request-path operation — it runs as a
standalone `alembic upgrade` invocation outside any HTTP request, so there
is no `structlog` request-id context to bind into
(`logging-observability.md` §1 doesn't apply here); it uses the stdlib
`logging` module instead, the conventional choice for Alembic data
migrations.

No `downgrade()` data-reversal is provided — reconstructing the original
key-keyed shape from an id-keyed one would require the same historical
key->id mapping this migration itself computed and discarded, and the
schema shape (JSONB) is unchanged either way, so `downgrade()` is a no-op:
an operator rolling back the application code to a pre-restructure version
would need to also restore a database backup taken before this migration
ran, not rely on this file to undo it.
"""

import logging
import uuid
from collections import Counter
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4b6f8a1c3e7"
down_revision: str | None = "6154ee8e944b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.restructure_walkin_payload_by_field_id")


def _target_schema() -> str:
    return op.get_context().version_table_schema


def _load_key_maps(
    conn: sa.engine.Connection, schema: str, branch_id: str | None
) -> tuple[dict[str, str], dict[str, str]]:
    """Returns `(field_key_to_id, group_key_to_id)` for one branch's
    currently live, non-deleted form — that branch's own rows, overlaid on
    the tenant-wide default scope (`branch_id IS NULL`) for any key the
    branch hasn't itself defined, matching `form_builder`'s branch-with-
    default-fallback scoping.
    """
    field_rows = conn.execute(
        text(
            f"""
            SELECT ff.key, ff.id, fs.branch_id
            FROM "{schema}".form_fields ff
            JOIN "{schema}".form_steps fs ON fs.id = ff.step_id
            WHERE ff.deleted_at IS NULL
              AND fs.deleted_at IS NULL
              AND (fs.branch_id = :branch_id OR fs.branch_id IS NULL)
            """
        ),
        {"branch_id": branch_id},
    ).fetchall()
    field_key_to_id: dict[str, str] = {}
    # Default-scope rows first, branch-specific rows second, so a
    # branch-specific field with the same key overrides the default one.
    for is_default in (True, False):
        for row in field_rows:
            row_is_default = row.branch_id is None
            if row_is_default != is_default:
                continue
            field_key_to_id[row.key] = str(row.id)

    group_rows = conn.execute(
        text(
            f"""
            SELECT fg.key, fg.id, fg.branch_id
            FROM "{schema}".form_field_groups fg
            WHERE fg.deleted_at IS NULL
              AND (fg.branch_id = :branch_id OR fg.branch_id IS NULL)
            """
        ),
        {"branch_id": branch_id},
    ).fetchall()
    group_key_to_id: dict[str, str] = {}
    for is_default in (True, False):
        for row in group_rows:
            row_is_default = row.branch_id is None
            if row_is_default != is_default:
                continue
            group_key_to_id[row.key] = str(row.id)

    return field_key_to_id, group_key_to_id


def _rekey(values: dict[str, Any], key_to_id: dict[str, str], orphans: Counter) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        field_id = key_to_id.get(key)
        if field_id is None:
            orphans[key] += 1
            result[key] = value
        else:
            result[field_id] = value
    return result


def _rekey_groups(
    group_values: dict[str, list[dict[str, Any]]],
    field_key_to_id: dict[str, str],
    group_key_to_id: dict[str, str],
    orphans: Counter,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for group_key, instances in group_values.items():
        group_id = group_key_to_id.get(group_key)
        if group_id is None:
            orphans[f"group:{group_key}"] += 1
            group_id = group_key
        result[group_id] = [_rekey(instance, field_key_to_id, orphans) for instance in instances]
    return result


def upgrade() -> None:
    schema = _target_schema()
    conn = op.get_bind()
    branch_maps: dict[str | None, tuple[dict[str, str], dict[str, str]]] = {}
    orphans: Counter = Counter()

    invitation_rows = conn.execute(
        text(
            f"""
            SELECT id, branch_id, custom_field_values,
                   primary_contact_custom_field_values, consents,
                   group_field_values
            FROM "{schema}".invitations
            """
        )
    ).fetchall()
    for row in invitation_rows:
        branch_key = str(row.branch_id) if row.branch_id else None
        if branch_key not in branch_maps:
            branch_maps[branch_key] = _load_key_maps(conn, schema, branch_key)
        field_key_to_id, group_key_to_id = branch_maps[branch_key]
        new_custom_field_values = _rekey(row.custom_field_values or {}, field_key_to_id, orphans)
        new_primary_contact_values = _rekey(
            row.primary_contact_custom_field_values or {}, field_key_to_id, orphans
        )
        new_consents = _rekey(row.consents or {}, field_key_to_id, orphans)
        new_group_field_values = _rekey_groups(
            row.group_field_values or {}, field_key_to_id, group_key_to_id, orphans
        )
        conn.execute(
            text(
                f"""
                UPDATE "{schema}".invitations
                SET custom_field_values = :custom_field_values,
                    primary_contact_custom_field_values = :primary_contact_custom_field_values,
                    consents = :consents,
                    group_field_values = :group_field_values
                WHERE id = :id
                """
            ).bindparams(
                sa.bindparam("custom_field_values", type_=sa.dialects.postgresql.JSONB),
                sa.bindparam(
                    "primary_contact_custom_field_values", type_=sa.dialects.postgresql.JSONB
                ),
                sa.bindparam("consents", type_=sa.dialects.postgresql.JSONB),
                sa.bindparam("group_field_values", type_=sa.dialects.postgresql.JSONB),
            ),
            {
                "id": row.id,
                "custom_field_values": new_custom_field_values,
                "primary_contact_custom_field_values": new_primary_contact_values,
                "consents": new_consents,
                "group_field_values": new_group_field_values,
            },
        )

    for table in ("invitation_visitors", "invitation_vehicles"):
        child_rows = conn.execute(
            text(
                f"""
                SELECT c.id, c.custom_field_values, i.branch_id
                FROM "{schema}".{table} c
                JOIN "{schema}".invitations i ON i.id = c.invitation_id
                """
            )
        ).fetchall()
        for row in child_rows:
            branch_key = str(row.branch_id) if row.branch_id else None
            if branch_key not in branch_maps:
                branch_maps[branch_key] = _load_key_maps(conn, schema, branch_key)
            field_key_to_id, _ = branch_maps[branch_key]
            new_values = _rekey(row.custom_field_values or {}, field_key_to_id, orphans)
            conn.execute(
                text(
                    f"""
                    UPDATE "{schema}".{table}
                    SET custom_field_values = :custom_field_values
                    WHERE id = :id
                    """
                ).bindparams(
                    sa.bindparam("custom_field_values", type_=sa.dialects.postgresql.JSONB),
                ),
                {
                    "id": row.id,
                    "custom_field_values": new_values,
                },
            )

    if orphans:
        logger.warning(
            "restructure_walkin_payload_by_field_id: %d distinct key(s) had no matching live "
            "field/group and were left un-migrated in schema '%s': %s",
            len(orphans),
            schema,
            dict(orphans),
        )


def downgrade() -> None:
    """No-op — see module docstring."""
