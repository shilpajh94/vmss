"""zone_gates_reference_devices: a gate is a security-mode device

Revision ID: d3a7c9e1b5f2
Revises: b9d4f1a6c3e8
Create Date: 2026-11-04 00:00:00.000000

add-zone-access-control: `zone_gates.gate_id` and `zone_access_events.gate_id`
now reference `devices.id` (the Security Gates list) instead of
`security_gates.id`; no `SecurityGate` rows exist in the product.

- `zone_gates`: rows pointing at `security_gates` cannot be mapped to devices, so
  they are removed (the links are re-made by choosing devices). The feature ships
  off by default, so none are expected in production.
- `zone_access_events`: it is an append-only ledger, so rows are kept. The new FK
  is added `NOT VALID` — enforced for new rows, existing rows not re-checked.
  Downgrade is symmetric.

Constraint names are looked up by reflection rather than assumed.
"""

from collections.abc import Sequence

from sqlalchemy import inspect, text

from alembic import op

revision: str = "d3a7c9e1b5f2"
down_revision: str | Sequence[str] | None = "b9d4f1a6c3e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _gate_fk_name(table: str, schema: str) -> str:
    for fk in inspect(op.get_bind()).get_foreign_keys(table, schema=schema):
        if fk["constrained_columns"] == ["gate_id"]:
            name = fk["name"]
            assert name is not None
            return name
    raise RuntimeError(f"{table}.gate_id has no foreign key")


def _repoint(referent: str, *, clear_links: bool) -> None:
    schema = op.get_context().version_table_schema
    conn = op.get_bind()
    if clear_links:
        conn.execute(text(f'DELETE FROM "{schema}".zone_gates'))
    for table, not_valid in (("zone_gates", False), ("zone_access_events", True)):
        op.drop_constraint(_gate_fk_name(table, schema), table, type_="foreignkey", schema=schema)
        suffix = " NOT VALID" if not_valid else ""
        conn.execute(
            text(
                f'ALTER TABLE "{schema}"."{table}" '
                f"ADD CONSTRAINT fk_{table}_gate_id_{referent} "
                f'FOREIGN KEY (gate_id) REFERENCES "{schema}"."{referent}" (id){suffix}'
            )
        )


def upgrade() -> None:
    _repoint("devices", clear_links=True)


def downgrade() -> None:
    _repoint("security_gates", clear_links=True)
