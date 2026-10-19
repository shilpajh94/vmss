"""Tenant migration `9d2b6f1c4a8e_add_whatsapp_contact_method_option`:
`whatsapp` is appended to the Preferred Contact Method field in the draft
`form_fields` row and in every published snapshot. Runs the revision's
`upgrade()` directly against the test tenant schema.
"""

import copy
import importlib.util
import uuid
from pathlib import Path
from typing import Any

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.form_builder.models import FormConfigVersion, FormField, FormStep

_TENANT_SCHEMA = "tenant_acme_test"
_MIGRATION = (
    Path(__file__).parents[1]
    / "alembic_tenant/versions/9d2b6f1c4a8e_add_whatsapp_contact_method_option.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("add_whatsapp_contact_method_option", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run_upgrade(db_session: AsyncSession) -> None:
    migration = _load_migration()

    def _upgrade(sync_conn) -> None:
        context = MigrationContext.configure(
            sync_conn, opts={"version_table_schema": _TENANT_SCHEMA}
        )
        with Operations.context(context):
            migration.upgrade()

    connection = await db_session.connection()
    await connection.run_sync(_upgrade)
    await db_session.commit()


def _field(step_id: uuid.UUID, key: str, field_type: str, order: int, **extra: Any) -> FormField:
    return FormField(
        id=uuid.uuid4(),
        step_id=step_id,
        key=key,
        label=key.replace("_", " ").title(),
        field_type=field_type,
        order_index=order,
        width="full",
        **extra,
    )


def _snapshot_field(row: FormField) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "stepId": str(row.step_id),
        "key": row.key,
        "label": row.label,
        "fieldType": row.field_type,
        "options": row.options,
        "orderIndex": row.order_index,
    }


async def test_migration_appends_whatsapp_to_draft_and_snapshots_idempotently(
    db_session: AsyncSession,
) -> None:
    step = FormStep(
        id=uuid.uuid4(), key="contact_details", name="Contact", order_index=0, is_active=True
    )
    db_session.add(step)
    await db_session.flush()
    contact = _field(
        step.id, "preferred_contact_method", "toggle_switch", 0, options=["email", "sms"]
    )
    other = _field(step.id, "registration_type", "toggle_switch", 1, options=["email", "sms"])
    db_session.add_all([contact, other])
    await db_session.flush()
    snapshot = [
        {
            "id": str(step.id),
            "key": "contact_details",
            "fields": [_snapshot_field(contact), _snapshot_field(other)],
        }
    ]
    version = FormConfigVersion(
        id=uuid.uuid4(), branch_id=None, version=1, snapshot=copy.deepcopy(snapshot)
    )
    db_session.add(version)
    contact_id, other_id, version_id = contact.id, other.id, version.id
    await db_session.commit()

    await _run_upgrade(db_session)

    db_session.expire_all()
    assert (await db_session.get(FormField, contact_id)).options == ["email", "sms", "whatsapp"]
    assert (await db_session.get(FormField, other_id)).options == ["email", "sms"]
    fields = (await db_session.get(FormConfigVersion, version_id)).snapshot[0]["fields"]
    assert [f["options"] for f in fields] == [["email", "sms", "whatsapp"], ["email", "sms"]]
    # Nothing but the options list changed.
    assert {k: v for k, v in fields[0].items() if k != "options"} == {
        k: v for k, v in snapshot[0]["fields"][0].items() if k != "options"
    }

    # Idempotent: a second run adds no duplicate.
    await _run_upgrade(db_session)
    db_session.expire_all()
    assert (await db_session.get(FormField, contact_id)).options == ["email", "sms", "whatsapp"]
    fields = (await db_session.get(FormConfigVersion, version_id)).snapshot[0]["fields"]
    assert fields[0]["options"] == ["email", "sms", "whatsapp"]
