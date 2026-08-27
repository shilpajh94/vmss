"""visit_info: seed visit_purposes and visit_durations

Revision ID: 09a7eeb963d3
Revises: 399f7463bd32
Create Date: 2026-08-24 00:00:01.000000

Seeds the exact six purposes / five durations already hardcoded in the app
today (visit-info-lookup-api-spec.md), so flipping the app from its fake
local list over to `GET /visit-info/options` is behavior-neutral on day one.
`sort_order` matches display order; `minutes` gives each duration a
machine-usable numeric value a display string can't carry.

"Full day" = 480 minutes assumes an 8-hour business day — not stated in the
source requirement doc, called out as an assumption
(openspec/changes/visit-info-lookup-api/design.md, Risks / Trade-offs).
Trivial to correct later since it's a data row, not a schema change.

Uses a real `sa.Table()` on a throwaway `sa.MetaData()`, never the
lightweight `sa.table()` helper — `sa.table()` does not participate in the
connection's `schema_translate_map` and would silently insert against the
wrong schema (verified gotcha from `8f3b6a19d5e2`'s data migration).
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "09a7eeb963d3"
down_revision: str | None = "399f7463bd32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PURPOSES = [
    "Business Meeting",
    "Job Interview",
    "Delivery / Pickup",
    "Personal Visit",
    "Vendor / Contractor Work",
    "Other",
]

_DURATIONS = [
    ("30 minutes", 30),
    ("1 hour", 60),
    ("2 hours", 120),
    ("Half day (4 hours)", 240),
    ("Full day", 480),
]


def _visit_purposes_table() -> sa.Table:
    return sa.Table(
        "visit_purposes",
        sa.MetaData(),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=255)),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("sort_order", sa.Integer()),
    )


def _visit_durations_table() -> sa.Table:
    return sa.Table(
        "visit_durations",
        sa.MetaData(),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=50)),
        sa.Column("minutes", sa.Integer()),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("sort_order", sa.Integer()),
    )


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        _visit_purposes_table().insert(),
        [
            {
                "id": uuid.uuid4(),
                "name": name,
                "is_active": True,
                "sort_order": index,
            }
            for index, name in enumerate(_PURPOSES)
        ],
    )
    bind.execute(
        _visit_durations_table().insert(),
        [
            {
                "id": uuid.uuid4(),
                "name": name,
                "minutes": minutes,
                "is_active": True,
                "sort_order": index,
            }
            for index, (name, minutes) in enumerate(_DURATIONS)
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        _visit_purposes_table().delete().where(
            _visit_purposes_table().c.name.in_(_PURPOSES)
        )
    )
    bind.execute(
        _visit_durations_table().delete().where(
            _visit_durations_table().c.name.in_([name for name, _ in _DURATIONS])
        )
    )
