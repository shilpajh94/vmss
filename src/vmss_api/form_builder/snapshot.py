"""Keeps stored form configuration readable after the field schema moves on
(heal-stale-form-config-data design.md Decisions 0 and 3).

A published snapshot is frozen JSON: one published before a key was added
to the field/group shape lacks that key, and one published before a field
type was removed still carries it. Served verbatim, either one makes a
strict client reject the whole form. `normalize_snapshot` brings any
snapshot up to the shape `service._step_to_snapshot` produces today, and
`is_supported_field_type` lets the admin reads skip rows of a removed type
instead of failing.
"""

import copy
from collections.abc import Iterable
from typing import Any, Protocol

from vmss_api.core.logging import logger
from vmss_api.form_builder.defaults import DEFAULT_EFFECTIVE_FORM
from vmss_api.form_builder.schemas import FormFieldType
from vmss_api.form_builder.step_icons import resolve_step_icon

SUPPORTED_FIELD_TYPES = frozenset(member.value for member in FormFieldType)

# Keys added to the snapshot field/group shape after snapshots were already
# being published, with the value an older snapshot implicitly meant. A key
# added to `service._step_to_snapshot` later must be added here too — the
# `test_normalized_snapshot_matches_current_shape` test fails until it is.
# (A group's `fieldIds` is also a later addition, but it's derived from
# `fieldKeys` rather than defaulted — see `_normalize_step`.)
SNAPSHOT_FIELD_DEFAULTS: dict[str, Any] = {"hideLabel": False}
SNAPSHOT_GROUP_DEFAULTS: dict[str, Any] = {"visibilityCondition": None}


class _FieldRow(Protocol):
    id: Any
    key: str
    field_type: str


def is_supported_field_type(field_type: object) -> bool:
    return isinstance(field_type, str) and field_type in SUPPORTED_FIELD_TYPES


def _warn_skipped(*, field_id: object, field_key: object, field_type: object, source: str) -> None:
    logger.warning(
        "form_field_unknown_type_skipped",
        field_id=str(field_id),
        field_key=field_key,
        field_type=field_type,
        source=source,
    )


def supported_field_rows[RowT: _FieldRow](rows: Iterable[RowT], *, source: str) -> list[RowT]:
    """Drops (and warns about) stored field rows whose type is no longer in
    the catalog, so an admin read serves the rest of the form rather than a
    500 from `FormFieldOut`'s enum."""
    kept = []
    for row in rows:
        if is_supported_field_type(row.field_type):
            kept.append(row)
        else:
            _warn_skipped(
                field_id=row.id, field_key=row.key, field_type=row.field_type, source=source
            )
    return kept


_LOCATION_FIELD_KEYS = ("branch", "building")


def _add_missing_location_fields(step: dict[str, Any]) -> None:
    """Snapshots published before `branch`/`building` became system fields
    of `visit_details` lack them; prepend them from the in-code defaults
    so clients render Location/Building without waiting on a republish."""
    if step.get("key") != "visit_details":
        return
    fields = step.get("fields", [])
    present = {f.get("key") for f in fields}
    default_step = next(s for s in DEFAULT_EFFECTIVE_FORM if s["key"] == "visit_details")
    missing = [
        copy.deepcopy(f)
        for f in default_step["fields"]
        if f["key"] in _LOCATION_FIELD_KEYS and f["key"] not in present
    ]
    if not missing:
        return
    for f in missing:
        f["stepId"] = step.get("id")
    for f in fields:
        f["orderIndex"] = f.get("orderIndex", 0) + len(missing)
    step["fields"] = missing + fields


def _normalize_step(step: dict[str, Any], *, source: str) -> dict[str, Any]:
    _add_missing_location_fields(step)
    # Snapshots published before steps were always given an icon carry
    # `"icon": null` (auto-assign-form-step-icons design.md Decision 3).
    step["icon"] = resolve_step_icon(step.get("icon"), step.get("name", ""))
    fields = []
    dropped_keys: set[str] = set()
    dropped_ids: set[str] = set()
    for field in step.get("fields", []):
        if not is_supported_field_type(field.get("fieldType")):
            _warn_skipped(
                field_id=field.get("id"),
                field_key=field.get("key"),
                field_type=field.get("fieldType"),
                source=source,
            )
            dropped_keys.add(field.get("key"))
            dropped_ids.add(field.get("id"))
            continue
        for key, default in SNAPSHOT_FIELD_DEFAULTS.items():
            field.setdefault(key, default)
        fields.append(field)
    step["fields"] = fields

    id_by_key = {field["key"]: field["id"] for field in fields}
    for group in step.get("groups", []):
        for key, default in SNAPSHOT_GROUP_DEFAULTS.items():
            group.setdefault(key, default)
        field_keys = [key for key in group.get("fieldKeys", []) if key not in dropped_keys]
        group["fieldKeys"] = field_keys
        if "fieldIds" in group:
            group["fieldIds"] = [i for i in group["fieldIds"] if i not in dropped_ids]
        else:
            # Snapshots published before by-id group membership: rebuild it
            # from the keys, which is what `validation.py` and the walk-in
            # payload mapping read.
            group["fieldIds"] = [id_by_key[key] for key in field_keys if key in id_by_key]
    return step


def normalize_snapshot(snapshot: list[dict[str, Any]], *, source: str) -> list[dict[str, Any]]:
    """A copy of `snapshot` in the current field/group shape: missing keys
    filled with their defaults, fields of unsupported types dropped (and
    warned about), group memberships pruned to match, a null step icon
    filled with the one its name infers. Values the snapshot does carry are
    otherwise left exactly as they are."""
    return [_normalize_step(step, source=source) for step in copy.deepcopy(snapshot)]
