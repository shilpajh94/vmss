## 1. Schema and Model

- [x] 1.1 Change `VisitDetailsSubmit.department_to_visit` in
      `invitations/schemas.py` from `str = Field(max_length=255)` to
      `str | None = Field(default=None, max_length=255)`. Done.
- [x] 1.2 Change `Invitation.department_to_visit` in
      `invitations/models.py` from `Mapped[str]` to `Mapped[str | None]`.
      **Already the case** — the model already declares
      `Mapped[str | None]` (models.py:103, under the "Visit details
      (self-registration only)" section, alongside `purpose_of_visit`/
      `host_name_or_email`/etc., all already nullable). No change needed.
- [x] 1.3 Author a new Alembic tenant revision dropping the `NOT NULL`
      constraint. **Not needed** — confirmed via `\d invitations` on both
      `vmss_test` and the dev `db` tenant schemas: `department_to_visit`
      already has no `NOT NULL` constraint at the DB level. The only
      constraint was in the Pydantic request schema (1.1), not the column.
- [x] 1.4 Apply the migration. **Not needed** — no migration was written
      (1.3 found nothing to migrate).

## 2. Service Layer

- [x] 2.1 Confirm `_resolve_visit_detail_ids` already handles a `None`
      free-text value correctly. Confirmed (service.py:194):
      `resolved["department_to_visit"] = visit_details.department_to_visit`
      passes the value straight through when `department_id` is absent —
      now correctly `None` rather than a required string. No code change
      needed.

## 3. Render-Site Audit

- [x] 3.1 Grep every `department_to_visit`/`departmentToVisit` read site.
      Confirmed complete set: `router.py` (OpenAPI examples + response
      construction, all response schemas already `str | None`),
      `schemas.py` (all response fields already `str | None`),
      `tasks.py` lines 138/345/356 (the only 3 sites that render/interpolate
      it). All tolerate `None`.
- [x] 3.2 Approval email's visit-detail section
      (`tasks.py:129-142`, the `visit_confirmation` template, feeding
      `_send_approval_notification`) — confirmed `visit_confirmation.html`
      guards with `{% if department %}` (core/email_templates/
      visit_confirmation.html:11), so a `None` department simply omits that
      row. No change needed.
- [x] 3.3 Plain-text fallback path in `invitations/tasks.py:345`
      (`_send_edit_notification`'s body string) already has
      `invitation.department_to_visit or 'Not specified'`. The same
      function's HTML path (`tasks.py:356`, the `edit` template) is also
      already guarded — confirmed `edit.html` uses
      `{% if department %}` (core/email_templates/edit.html:11) identically
      to `visit_confirmation.html`. No other plain-text body interpolates
      `department_to_visit` (confirmed by the grep in 3.1 — only these 3
      `tasks.py` sites exist). No change needed.

## 4. Tests

- [x] 4.1 Added `test_create_invitation_with_no_department_succeeds_and_leaves_it_unset`
      (invitations/tests.py) and
      `test_walk_in_registration_with_no_department_succeeds_and_leaves_it_unset`
      (registrations/tests.py) — both pass. (Note: the create-response
      shape, `InvitationOut`, doesn't surface `departmentToVisit` at all —
      it's a lean summary — so both tests assert via
      `InvitationRepository.get_by_tracking_id`, matching the sibling
      `test_create_invitation_ignores_supplied_host_fields`'s pattern.)
- [x] 4.2 Confirmed: `test_create_invitation_with_no_ids_behaves_exactly_as_before`,
      `test_create_invitation_with_ids_overwrites_free_text_with_canonical_value`,
      `test_create_invitation_unknown_purpose_id_rejected`,
      `test_create_invitation_cross_tenant_purpose_id_rejected` all still
      pass unchanged.
- [x] 4.3 Added `test_edit_invitation_sets_a_previously_unset_department`
      (invitations/tests.py) — passes.
- [x] 4.4 Confirmed via grep — no existing test in any of the three files
      asserts a rejection for an omitted `departmentToVisit`; every
      reference is a positive payload value or one of the new tests above.
      Full-file run of all three: 304 passed.

## 5. Docs and Closing Gate

- [x] 5.1 Updated `docs/features/invitations.md` with a new
      "`departmentToVisit` is optional at creation" note, mirroring the
      existing `hostId`/`hostNameOrEmail` note's style.
- [x] 5.2 Full suite green twice in a row: 826 passed, 826 passed (up from
      823 — the 3 new tests added in section 4).
- [x] 5.3 `ruff check .` clean. `ruff format --check .` clean aside from the
      one pre-existing, unrelated markdown note (task 1.2 of
      `verify-full-api-test-and-validation-coverage`, already documented as
      out of scope).
- [x] 5.4 `mypy` on `core`/`auth`/`notifications`/`identity_verification`
      plus `invitations` (the only other module this change touched):
      clean, 59 source files.
