"""repeatable field groups: form_field_groups, form_fields.group_id,
invitations.group_field_values

Revision ID: b8e3f4a1c6d2
Revises: f74620cd4ffa
Create Date: 2026-09-22 00:00:00.000000

Adds the `FormFieldGroup` construct (`specs/form-builder/spec.md` "A Step's
Fields May Be Organized Into Named, Repeatable Field Groups") — a step's
fields can now be clustered into named groups, optionally repeatable with a
configurable min/max instance count, generalizing Vehicle Info's/Visitor
Info's previously hard-coded "add another" behavior
(`openspec/changes/add-repeatable-field-groups/design.md`).

Three schema changes:
- New `form_field_groups` table (mirrors `form_steps`'s branch/default-scope
  partial-unique-index pattern for branch-wide group-key uniqueness).
- `form_fields.group_id`, nullable FK to `form_field_groups.id` — a field
  with no group assignment stays a flat step-level field, unchanged from
  before groups existed.
- `invitations.group_field_values`, JSONB, for any repeatable group other
  than the seeded Vehicle Info/Visitor Info groups (which keep their
  existing `InvitationVehicle`/`InvitationVisitor` tables — design.md
  Decision 2/3). Purely additive, no backfill needed (defaults to `{}`).

Data backfill: every existing branch (and the tenant default, `branch_id
IS NULL`) that already has a Vehicle Info or Visitor Info step gets that
step's seeded locked group row, and the step's existing fields matching the
known field keys get `group_id` set to it — see design.md Migration Plan
step 2. `FormConfigVersion` snapshots already published before this
migration are NOT regenerated here: `form_builder/validation.py`'s group
lookups (`_find_group`, `custom_groups_for_invitation_scope`) use `dict.get`
with an empty-list default, so a pre-existing snapshot with no `"groups"`
key simply yields "no group found" — `validate_group_instance_count` then
no-ops, which is exactly today's actual (unlimited) Vehicle Info behavior.
No tenant's live validation changes until an admin publishes again, and a
brand-new publish (this migration's backfilled draft rows) already produces
a `"groups"`-bearing snapshot.

Every statement against `form_field_groups` (a table this migration
creates) relies on the connection's `schema_translate_map` alone. Every
statement against `form_fields`/`invitations` (pre-existing tables) passes
`schema=` explicitly (`275bc2310f49`'s documented `op.add_column` gotcha).
The backfill queries/inserts use a real `sa.Table()` on a throwaway
`MetaData()` for `form_steps`/`form_fields` reads (not `sa.table()` — see
`c3e5aadc345f`'s docstring for why), and schema-qualified raw `text()` SQL
for the `form_field_groups`/`form_fields` writes, since `text()` never
honors `schema_translate_map`.

Hand-written, not `alembic revision --autogenerate` — same
`include_schemas=True` cross-schema-FK reflection limitation as every other
migration in this tree.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e3f4a1c6d2"
down_revision: str | None = "f74620cd4ffa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOT_DELETED = sa.text("deleted_at IS NULL")

# (step key, group key, group name, field keys belonging to that group) —
# matches `form_builder/defaults.py`'s `DEFAULT_STEP_SPECS` group_key
# assignments for Vehicle Info/Visitor Info.
_SYSTEM_GROUPS: list[tuple[str, str, str, list[str]]] = [
    (
        "vehicle_info",
        "vehicles",
        "Vehicles",
        ["vehicle_type", "license_plate", "make_model", "color"],
    ),
    (
        "visitor_info",
        "visitors",
        "Visitors",
        ["full_name", "email", "phone", "id_proof_type", "id_proof_upload", "profile_photo"],
    ),
]


def _target_schema() -> str:
    return op.get_context().version_table_schema


def upgrade() -> None:
    schema = _target_schema()

    op.create_table(
        "form_field_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("is_repeatable", sa.Boolean(), nullable=False),
        sa.Column("min_instances", sa.Integer(), nullable=True),
        sa.Column("max_instances", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["step_id"], [f"{schema}.form_steps.id"]),
        sa.ForeignKeyConstraint(["branch_id"], [f"{schema}.branches.id"]),
    )
    op.create_index(
        "ix_form_field_groups_step_id", "form_field_groups", ["step_id"], schema=schema
    )
    op.create_index(
        "ix_form_field_groups_branch_id", "form_field_groups", ["branch_id"], schema=schema
    )
    op.create_index(
        "uq_form_field_group_branch_key",
        "form_field_groups",
        ["branch_id", "key"],
        unique=True,
        schema=schema,
        postgresql_where=sa.text("deleted_at IS NULL AND branch_id IS NOT NULL"),
    )
    op.create_index(
        "uq_form_field_group_default_key",
        "form_field_groups",
        ["key"],
        unique=True,
        schema=schema,
        postgresql_where=sa.text("deleted_at IS NULL AND branch_id IS NULL"),
    )

    op.add_column("form_fields", sa.Column("group_id", sa.Uuid(), nullable=True), schema=schema)
    op.create_foreign_key(
        "fk_form_fields_group_id",
        "form_fields",
        "form_field_groups",
        ["group_id"],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index("ix_form_fields_group_id", "form_fields", ["group_id"], schema=schema)

    op.add_column(
        "invitations",
        sa.Column(
            "group_field_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema=schema,
    )

    _backfill_system_groups(schema)


def _backfill_system_groups(schema: str) -> None:
    bind = op.get_bind()
    metadata = sa.MetaData(schema=schema)
    form_steps = sa.Table(
        "form_steps",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("branch_id", sa.Uuid()),
        sa.Column("key", sa.String()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )

    for step_key, group_key, group_name, field_keys in _SYSTEM_GROUPS:
        steps = bind.execute(
            sa.select(form_steps.c.id, form_steps.c.branch_id).where(
                form_steps.c.key == step_key, form_steps.c.deleted_at.is_(None)
            )
        ).fetchall()
        for step_row in steps:
            group_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    f'INSERT INTO "{schema}".form_field_groups '
                    f"(id, step_id, branch_id, key, name, is_system, is_locked, "
                    f"is_repeatable, min_instances, max_instances, order_index, "
                    f"created_at, updated_at) "
                    f"VALUES (:id, :step_id, :branch_id, :key, :name, true, true, "
                    f"true, NULL, NULL, 0, now(), now())"
                ),
                {
                    "id": group_id,
                    "step_id": step_row.id,
                    "branch_id": step_row.branch_id,
                    "key": group_key,
                    "name": group_name,
                },
            )
            bind.execute(
                sa.text(
                    f'UPDATE "{schema}".form_fields '
                    f"SET group_id = :group_id "
                    f"WHERE step_id = :step_id AND key = ANY(:field_keys) "
                    f"AND deleted_at IS NULL"
                ),
                {"group_id": group_id, "step_id": step_row.id, "field_keys": field_keys},
            )


def downgrade() -> None:
    schema = _target_schema()
    op.drop_column("invitations", "group_field_values", schema=schema)
    op.drop_index("ix_form_fields_group_id", table_name="form_fields", schema=schema)
    op.drop_constraint(
        "fk_form_fields_group_id", "form_fields", schema=schema, type_="foreignkey"
    )
    op.drop_column("form_fields", "group_id", schema=schema)
    op.drop_table("form_field_groups", schema=schema)
