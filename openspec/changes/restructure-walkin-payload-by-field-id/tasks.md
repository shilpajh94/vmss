## 1. Form Builder: id-based resolution helpers

- [x] 1.1 `form_builder/defaults.py`/`service.py` now attach a `fieldIds`
      list to every group snapshot (alongside the pre-existing `fieldKeys`,
      kept for the key-based lookups that are explicitly out of scope —
      see design.md Non-Goals), so group membership can resolve by id.
- [x] 1.2 `custom_fields_for_step`/`custom_fields_for_invitation_scope`
      needed no change (no key/id lookup inside them);
      `custom_groups_for_invitation_scope`/`custom_groups_for_step` now
      resolve member fields via `fieldIds`/`fields_by_id` and
      `custom_groups_for_step` returns its dict keyed by group `id`.
- [x] 1.3 Renamed to `allowed_consent_field_ids`/`required_consent_field_ids`,
      resolving the Consent Agreement step's fields by `id`.
- [x] 1.4 `validate_custom_field_values` now takes an id-keyed `values` dict
      (`{str(fieldId): value}`) and resolves fields via `fields_by_id`; an
      unresolvable id (unknown, inactive, or wrong branch/tenant) is
      rejected identically — no separate code path (design.md Decision 5).
- [x] 1.5 `_find_field_by_key` was **kept**, not removed — it's still needed
      for the *retyped-system-field* option lookups (`idProofType`,
      `vehicleType`, etc.), which are an explicit Non-Goal, not part of the
      key→id migration. Nothing key-based remains in the actual
      admin-authored EAV path.

## 2. Invitations: request/response schemas

- [x] 2.1 Added `CustomFieldValue`, `ConsentValue`, `FieldGroupSubmit`, and
      a response-side `FieldGroupValuesOut` in `invitations/schemas.py`.
- [x] 2.2 `VisitorSubmit`/`InvitationPrimaryContactCreate`/`VehicleSubmit`/
      `InvitationCreate` now declare `custom_fields: list[CustomFieldValue]`
      on the wire; each also exposes a `custom_field_values` **property**
      (`{str(fieldId): value}`) so the rest of the codebase's internal dict-
      based logic didn't need a parallel rewrite (design.md Decision 3.2).
- [x] 2.3 `InvitationCreate.consents` is now `list[ConsentValue]`, with a
      `consents_dict` property for internal use.
- [x] 2.4 `groups: list[FieldGroupSubmit]` replaces `group_values`, with a
      `group_values` property (`{str(groupId): [{str(fieldId): value}, ...]}`)
      for internal use.
- [x] 2.5 `_check_visitor_list_matches_registration_type` now reads
      `self.groups`/`group.instances`.
- [x] 2.6 Every `*Out` schema's `custom_field_values`/
      `primary_contact_custom_field_values` is now `custom_fields`/
      `primary_contact_custom_fields: list[CustomFieldValue]`;
      `group_field_values` is `groups: list[FieldGroupValuesOut]`;
      `consents` is `list[ConsentValue]`.
- [x] 2.7 `_PAYLOAD_DESCRIPTION`, both example payloads, and the
      `create_invitation`/`_parse_prefixed_multipart_files` docstrings
      updated to the id-referenced shape.

## 3. Invitations: service/router logic

- [x] 3.1 `create_invitation` rewritten: consent/group lookups now use the
      id-based helpers; `payload.consents_dict`/`.custom_field_values`/
      `.group_values` properties feed the (unchanged-shape) internal dict
      logic; file-upload field-id sets (`visitor_info_file_ids`, etc.)
      replace the old key sets; `_group_field_file_key` renamed
      `_group_field_file_id`.
- [x] 3.2 Persistence unchanged in column type — the dicts written are now
      naturally id-keyed since they're built from the id-keyed properties/
      helpers above (`consents=dict(consents_dict)` is the one explicit
      rename needed).
- [x] 3.3 `_resolve_custom_field_file_values`/`_resolve_group_field_values`
      take `file_ids`; new `_dict_to_custom_fields`/`_dict_to_consents`/
      `_dict_to_groups` convert the stored dict shape to the wire's
      `list[...]` shape at every response-construction site.
- [x] 3.4 File-upload matching (`primaryContactCustomFieldFiles[<fieldId>]`
      etc.) now keys by field id throughout service.py and router.py.

## 4. Registrations

- [x] 4.1 Confirmed `WalkInRegistrationCreate`/`Out` (re-exports) pick up
      the new shape automatically; updated `registrations/router.py`'s
      docstring referencing `groupFieldFiles[<groupKey>]`/`[<fieldKey>]`.

## 5. Data migration

- [x] 5.1 `alembic_tenant/versions/d4b6f8a1c3e7_backfill_custom_field_answers_by_id.py`
      — per-branch (with tenant-default-scope fallback) key→id backfill for
      `invitations`/`invitation_visitors`/`invitation_vehicles`. **Not run
      against a real tenant schema in this session** — written and
      reviewed, but unexercised; treat as needing a dry run before
      production use.
- [x] 5.2 Logs an aggregate per-schema `WARNING` (stdlib `logging`, not
      `structlog` — see the migration's own docstring for why) of every
      distinct un-migrated key.

## 6. Tests

- [x] 6.1 `factories.py`'s `InvitationFactory`/`InvitationVisitorFactory`/
      `InvitationVehicleFactory` now default the JSONB answer columns to
      `{}` (polyfactory's random-string auto-values are never valid UUIDs);
      `invitations/tests.py`/`registrations/tests.py`'s `_individual_payload`/
      `_group_payload` submit `consents` via a deterministic default-form
      field id (`form_builder/defaults.py::_stable_id`); every custom-field/
      group test in both files rewritten to the id-based shape.
- [x] 6.2 Renamed to `test_create_invitation_custom_field_unresolvable_id_rejected`
      / `test_walk_in_registration_custom_field_unresolvable_id_rejected`,
      submitting a random UUID instead of an unknown key.
- [ ] 6.3 **Not added** — no test explicitly covers a `fieldId`/`groupId`
      that resolves on a *different* branch/tenant (only the "doesn't
      exist at all" case is covered, via 6.2's random-UUID rejection).
- [ ] 6.4 **Not added** — the migration (§5) has no test coverage yet.
- [ ] 6.5 **Not added** — no camelCase-rendering assertion added for the
      three new schemas.
- [x] Verification actually run this session: `form_builder/tests.py`
      (101/101 pass, unaffected). `invitations/tests.py`: went from 126
      failed/208 passed (pre-fix baseline) to a large majority passing
      after the fixture/test rewrite — see the change's implementation
      notes for the exact final count, and re-run before merging since the
      last observed run in this session was not read to completion.
      `registrations/tests.py` hit a pre-existing, apparently unrelated
      test-infrastructure failure (`registration_device_keys_tenant_id_fkey`
      FK violation in the `registration_device_raw_key` fixture, reproducible
      in complete isolation, before any of this change's code runs) — not
      something this change introduced (verified: `invitations/tests.py`
      uses the same shared `tenant` fixture successfully hundreds of times
      in the same run), but it blocked getting a clean pass count for that
      file. Needs investigation independent of this change.

## 7. Docs

- [x] 7.1 `docs/features/invitations.md` and `docs/features/registrations.md`
      updated for the sections directly describing the payload wire shape
      (consents/customFields/groups, file-upload multipart conventions).
      Not a full line-by-line audit of either (large, ~900-line) file —
      re-read before merging for anything missed.
- [ ] 7.2 **Not done** — requires actually contacting the React portal/
      Flutter app teams, which this session cannot do.

## 8. Archive sequencing (process, not code)

- [ ] 8.1 Still applies unchanged: before archiving this change, confirm
      `add-generic-custom-field-support` and `add-repeatable-field-groups`
      are archived first (or in the same batch, in that order) — see
      design.md Decision 3.
