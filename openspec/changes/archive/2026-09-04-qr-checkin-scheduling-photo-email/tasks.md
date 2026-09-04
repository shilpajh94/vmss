## 1. QR Check-In Scheduled-Date Gate

- [x] 1.1 Add a local tenant-timezone-resolution helper in
      `invitations/service.py` (mirrors `dashboard/service.py`'s
      `_resolve_tenant_timezone`: `ZoneInfo(tenant.timezone)`, falling back to
      `ZoneInfo("UTC")` with a `WARNING` log on an invalid stored value).
- [x] 1.2 In `check_in_by_qr_token`, add a check (alongside the existing
      `expires_at` check) that rejects the scan with `HTTP_425_TOO_EARLY` and
      detail `"Verification failed — visit window not yet open"` when
      `invitation.preferred_visit_date` is set and is later than the current
      date in the tenant's local timezone. Skip the check entirely when
      `preferred_visit_date` is `None`.
- [x] 1.3 Extend `repository.py::check_in_by_qr_if_eligible`'s atomic
      `UPDATE ... WHERE` clause with the equivalent scheduled-date condition
      (tenant-local date comparison), so the race-safety guarantee matches the
      existing `expires_at > now()` clause. Confirm the tenant-local "today"
      value is computed once per call and passed in, not recomputed per row.
- [x] 1.4 Update `_QR_ENTRY_ELIGIBLE_STATUSES`-adjacent logic/comments if
      needed so the new condition is documented next to the existing
      eligibility constants.
- [x] 1.5 Tests in `invitations/tests.py`: scan rejected with 425 before the
      scheduled date; scan succeeds on the scheduled date at an arbitrary time
      of day; scan succeeds after the scheduled date (existing behavior,
      unchanged); scan with no `preferred_visit_date` set falls back to
      expiry-only gating (existing behavior, unchanged); scan still rejected
      with 410 when expired, independent of the scheduled-date check; the two
      rejection reasons are distinguishable by status code.

## 2. Profile Photo on Invitation List

- [x] 2.1 Add a nullable primary-contact photo URL field to the list-row
      response schema in `invitations/schemas.py` (`CamelModel` subclass,
      consistent with `primary_contact_photo_url` on the existing detail
      schemas).
- [x] 2.2 Wire the field into the list endpoint's row construction in
      `invitations/router.py`, reusing the existing `_resolve_photo_url()`
      helper — no new repository query or relationship load required (the
      storage key is already a plain column on the loaded `Invitation` row).
- [x] 2.3 Update `docs/features/invitations.md` to document the new list
      response field.
- [x] 2.4 Tests in `invitations/tests.py`: list row includes a resolvable
      photo URL when the primary contact has a stored photo; list row's photo
      field is null when no photo was captured; existing list-endpoint tests
      (pagination, filtering, sorting, branch-scoping, permission-denied)
      still pass unchanged.

## 3. Host Email Notification on Invitation Creation

- [x] 3.1 Add a new Celery task in `invitations/tasks.py` (e.g.
      `send_host_creation_notification`), following the existing
      `_RETRY_KWARGS` / `tenant_session_scope` / idempotent-lookup /
      `_dispatch()` shape used by `send_approval_notification`.
- [x] 3.2 In the task body, resolve the host's email via
      `UserRepository(tenant_db).get_active(invitation.host_id)` and compose
      the "invitation received" email subject/body; no-op (return early) if
      the invitation or the host no longer resolves (idempotency /
      soft-delete safety per `background-jobs.md` §2).
- [x] 3.3 In `create_invitation` (`invitations/service.py`), after the
      existing commit, enqueue the new task with `.delay(...)` when
      `invitation.host_id` is present, passing `request_id`,
      `tenant_schema`, and `invitation_id` following the existing call
      pattern (e.g. `tasks.send_approval_notification.delay(...)` at
      lines 505-510). Skip enqueueing when no host resolved.
- [x] 3.4 Confirm/add the `ERROR`-level exhausted-retries log statement in the
      new task includes `tenant_id`, `invitation_id`, and the host's user id,
      per `logging-observability.md` §2/§3 and `background-jobs.md` §4.
- [x] 3.5 Tests in `invitations/tests.py`: creation with a resolved host
      enqueues/dispatches the host email (verified via the real mail catcher,
      consistent with the existing "Visit-Confirmation Dispatch Is Verified
      Against a Real Mail Catcher" test pattern); creation with no resolved
      host does not dispatch it and still succeeds; creation response is not
      delayed by the dispatch; auto-approved creation still sends the host
      email (independent of the submission-push logic).

## 4. Check-In/Check-Out Toggle Regression Guard

- [x] 4.1 Confirm whether `invitations/tests.py` already has a test asserting
      that a QR scan of an already-`checked_in` invitation returns 409 without
      changing `checkInStatus` (per the existing, unchanged spec scenario
      "Calling check-in while already checked in is rejected"). If missing,
      add it; if present, leave it as-is. **Confirmed present**:
      `test_qr_check_in_while_already_checked_in_rejected` (tests.py:3497) —
      left unchanged.
- [x] 4.2 No production code change for this item — `check_in_by_qr_token`
      already implements the correct (non-toggling) behavior. Note this
      explicitly in the PR description so the original front-end report is
      addressed without an unnecessary code change.

## 5. Verification

- [x] 5.1 `ruff check` and `ruff format --check` clean on all touched files.
- [x] 5.2 `mypy` clean (invitations is not in the strict-typing scope per
      `project-rules.md`, but keep existing type-hint discipline).
- [x] 5.3 Full `pytest` suite green, including the new tests above and the
      existing permission-denied / tenant-isolation cases already covering
      `invitations`. (789 passed, full suite.)
- [x] 5.4 Update `docs/features/invitations.md` for the QR check-in
      scheduled-date behavior and the host-email dispatch (in addition to the
      list-field doc update in 2.3).
