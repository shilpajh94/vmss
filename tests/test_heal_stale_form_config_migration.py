"""Tenant migration `c3d5e7f9a1b2_heal_stale_form_config_data`
(heal-stale-form-config-data): removed field types are remapped and old
snapshot keys backfilled, in `form_fields` rows and every published
snapshot. Runs the revision's `upgrade()` directly against the test
tenant schema through an Alembic operations context.
"""

import copy
import importlib.util
import uuid
from pathlib import Path
from typing import Any

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.form_builder.models import FormConfigVersion, FormField, FormStep

_TENANT_SCHEMA = "tenant_acme_test"
_MIGRATION = (
    Path(__file__).parents[1]
    / "alembic_tenant/versions/c3d5e7f9a1b2_heal_stale_form_config_data.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("heal_stale_form_config_data", _MIGRATION)
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


def _field(step_id: uuid.UUID, key: str, field_type: str, **extra: Any) -> FormField:
    return FormField(
        id=uuid.uuid4(),
        step_id=step_id,
        key=key,
        label=key.replace("_", " ").title(),
        field_type=field_type,
        order_index=extra.pop("order_index", 0),
        width="full",
        **extra,
    )


def _snapshot_field(row: FormField) -> dict[str, Any]:
    # The pre-`hideLabel` field shape.
    return {
        "id": str(row.id),
        "stepId": str(row.step_id),
        "groupId": None,
        "key": row.key,
        "label": row.label,
        "placeholder": None,
        "helpText": row.help_text,
        "fieldType": row.field_type,
        "isSystem": False,
        "isLocked": False,
        "isActive": True,
        "isRequired": row.is_required,
        "options": row.options,
        "validationRules": None,
        "visibilityCondition": None,
        "width": "full",
        "orderIndex": row.order_index,
    }


async def test_migration_remaps_removed_types_and_backfills_old_snapshot_keys(
    db_session: AsyncSession,
) -> None:
    step = FormStep(
        id=uuid.uuid4(), key="visitor_info", name="Visitor Info", order_index=0, is_active=True
    )
    db_session.add(step)
    await db_session.flush()
    terms = _field(
        step.id,
        "terms_conditions",
        "signature_pad",
        help_text="By visiting you agree to the site rules.",
        is_required=False,
        options=["unused"],
    )
    rich = _field(step.id, "welcome_note", "rich_text_block", order_index=1)
    table = _field(step.id, "item_table", "dynamic_table", options=["a", "b"], order_index=2)
    email = _field(step.id, "email", "email", is_required=True, order_index=3)
    deleted = _field(step.id, "old_sig", "signature_pad", order_index=4)
    db_session.add_all([terms, rich, table, email, deleted])
    await db_session.flush()
    deleted_id = deleted.id
    await db_session.execute(
        FormField.__table__.update()
        .where(FormField.id == deleted_id)
        .values(deleted_at=FormField.created_at)
    )
    old_snapshot = [
        {
            "id": str(step.id),
            "key": "visitor_info",
            "name": "Visitor Info",
            "fields": [_snapshot_field(f) for f in (terms, rich, table, email)],
            # The pre-`visibilityCondition`/`fieldIds` group shape.
            "groups": [{"id": str(uuid.uuid4()), "key": "contact", "fieldKeys": ["email"]}],
        }
    ]
    version = FormConfigVersion(
        id=uuid.uuid4(), branch_id=None, version=1, snapshot=copy.deepcopy(old_snapshot)
    )
    db_session.add(version)
    step_id, terms_id, email_id, version_id = step.id, terms.id, email.id, version.id
    await db_session.commit()

    await _run_upgrade(db_session)

    db_session.expire_all()
    rows = {
        f.key: f
        for f in (await db_session.execute(select(FormField).where(FormField.step_id == step_id)))
        .scalars()
        .all()
    }
    assert (rows["terms_conditions"].field_type, rows["terms_conditions"].options) == (
        "checkbox_single",
        None,
    )
    assert rows["terms_conditions"].help_text == "By visiting you agree to the site rules."
    assert rows["terms_conditions"].is_required is False
    assert rows["terms_conditions"].id == terms_id
    assert rows["welcome_note"].field_type == "static_text"
    assert (rows["item_table"].field_type, rows["item_table"].options) == ("textarea", None)
    assert rows["email"].field_type == "email"
    assert rows["old_sig"].field_type == "checkbox_single", "soft-deleted rows are healed too"

    healed = (await db_session.get(FormConfigVersion, version_id)).snapshot
    by_key = {f["key"]: f for f in healed[0]["fields"]}
    assert by_key["terms_conditions"]["fieldType"] == "checkbox_single"
    assert by_key["terms_conditions"]["options"] is None
    assert by_key["welcome_note"]["fieldType"] == "static_text"
    assert by_key["item_table"]["fieldType"] == "textarea"
    assert all(f["hideLabel"] is False for f in healed[0]["fields"])
    group = healed[0]["groups"][0]
    assert group["visibilityCondition"] is None
    assert group["fieldIds"] == [str(email_id)]
    # Nothing it carried was changed beyond the remap and the new keys.
    original = {f["key"]: f for f in old_snapshot[0]["fields"]}
    for key, field in by_key.items():
        unchanged = {
            k: v for k, v in field.items() if k not in {"fieldType", "options", "hideLabel"}
        }
        assert unchanged == {
            k: v for k, v in original[key].items() if k not in {"fieldType", "options"}
        }

    # Idempotent: a second run leaves everything exactly as it was.
    await _run_upgrade(db_session)
    db_session.expire_all()
    assert (await db_session.get(FormConfigVersion, version_id)).snapshot == healed
