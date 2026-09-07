## 1. Check-In Endpoint Consolidation

- [x] 1.1 Remove the `PATCH /api/v1/invitations/{id}/check-in` route and its
      handler function from `invitations/router.py`; remove any
      now-unreferenced service/schema code exclusive to it (keep
      `check_in_invitation` in `invitations/service.py` if the v2 route
      still calls it — only delete what becomes dead).
- [x] 1.2 Update `invitations/router.py`'s OpenAPI tags/docstrings so the v2
      tracking-ID check-in route's docstring no longer refers to itself as
      "the replacement" for a route that no longer exists.
- [x] 1.3 Add `trackingId` to the upcoming-visitors preview row in
      `dashboard/service.py`'s overview computation (or confirm it is
      already present and skip this task with a note in the PR). — Already
      present (`UpcomingVisitorOut.tracking_id`); added a regression test
      instead of a code change.
- [x] 1.4 Remove the `PATCH /admin/dashboard/upcoming-visitors` route,
      handler, and request schema from `dashboard/router.py`/`schemas.py`;
      remove `dashboard/service.py` code exclusive to it.
- [x] 1.5 Update `invitations/tests.py` to drop v1 check-in route tests,
      confirm v2 tracking-ID check-in tests already cover the same
      eligibility rules (approved-only, watchlist-block, permission-denied,
      idempotency), adding any missing case.
- [x] 1.6 Update `dashboard/tests.py` to drop the upcoming-visitors
      check-in mutation tests and add a test asserting the overview
      preview row includes `trackingId`.
- [x] 1.7 Update `docs/features/invitations.md` and
      `docs/features/dashboard.md` to remove the retired endpoints and add
      a `Deprecation`/removal note per `api-conventions.md` §2.

## 2. QR Check-In / Check-Out Split

- [x] 2.1 In `invitations/service.py`, remove the if/else toggle from
      `check_in_by_qr_token`; leave it handling only the
      unused/checked_out → checked_in transition (with the existing
      approved/watchlist/expiry checks).
- [x] 2.2 Add `check_out_by_qr_token` to `invitations/service.py`, backing
      it with the existing `InvitationRepository.check_out_by_qr_if_eligible`
      call moved out of the old else-branch; no expiry check on this path.
- [x] 2.3 Add the `PATCH /api/v2/invitations/qr/{token}/check-out` route to
      `invitations/router.py` (`router_v2`), rate-limited the same as the
      existing QR check-in route.
- [x] 2.4 Update `check_in_by_qr_token`'s router docstring to state it no
      longer toggles and now returns 409 when already `checked_in`.
- [x] 2.5 Update `invitations/tests.py`: split existing toggle-behavior
      tests into check-in-only and check-out-only cases; add a test for
      calling check-in while already `checked_in` (expect 409, no state
      change) and calling check-out while not `checked_in` (expect 409, no
      state change); keep the existing expiry-on-entry and
      expiry-does-not-block-exit tests, retargeted at the two endpoints.

## 3. relevantToMe: Role-Based Current-Step Approver Visibility

- [x] 3.1 In `invitations/repository.py::_relevant_to_me_filter`, add the
      third `or_()` branch: an `EXISTS` subquery matching an invitation
      whose current pending `InvitationApprovalStep` (lowest `stepOrder`
      among `pending` steps) has `approverRoleId` set, `delegated_to_user_id
      IS NULL`, and the caller holds that role via `UserBranchRole` at the
      step's/invitation's branch (or company-wide) — reuse the same
      role-lookup shape `approvals/service.py::_user_holds_role_at_branch`
      already uses, factored into a shared helper if not already
      importable from `repository.py`.
- [x] 3.2 Confirm "current pending step" is computed consistently with how
      `approvals/service.py` determines it (lowest `stepOrder` still
      `pending`) — extract to a shared query fragment if duplicated.
- [x] 3.3 Add tests in `invitations/tests.py` for: a role-holder sees the
      invitation via `relevantToMe=true`; a role-holder loses visibility
      once the step is delegated to someone else; a role-holder whose role
      doesn't match the current step sees nothing; composition with
      `status` filtering still works for the new clause. (Existing
      `relevantToMe` status-filter composition test already covered the
      host case generically; the new role-holder tests cover the added
      clause specifically.)
- [x] 3.4 Add a tenant-isolation test confirming a role-holder in a
      different tenant's schema never sees another tenant's invitation via
      this clause (per `testing-standards.md` §2), even if a same-named
      role exists in both.

## 4. Delegation Generalization

- [x] 4.1 In `approvals/service.py`, extract the existing "can this caller
      act on this step" logic into a shared predicate (e.g.
      `_caller_can_act_on_step(step, caller, branch_id)`), used by both the
      approve/reject action path and `delegate_step`.
- [x] 4.2 Rewrite `delegate_step` to: (a) load the invitation's current
      pending step regardless of `stepOrder`, (b) authorize the caller via
      the shared predicate from 4.1 (role match / host match / delegate
      match / override), (c) validate the named delegate against the
      step's own kind (role-holder for role-identified, `invitations:approve`
      holder for host-identified `stepOrder` 0), (d) allow overwriting an
      existing `delegated_to_user_id` rather than rejecting when one is
      already set, guarded by the same authorization check (so only the
      current delegate or an override-holder can re-delegate).
- [x] 4.3 Update `InvitationApprovalStepRepository.delegate_if_eligible`
      (`approvals/repository.py`) to allow the update when a delegate is
      already set, provided the caller-authorization check in 4.2 already
      passed — keep the race-safe single-statement update, just relax the
      "must currently be NULL" guard to "must match the authorization rule
      already evaluated." Implemented as a compare-and-swap on the
      previously-observed delegate (`expected_current_delegate_id`) rather
      than a bare relaxation, to keep the same concurrency-safety guarantee
      for the re-delegation case.
- [x] 4.4 Update `approvals/router.py`'s delegate endpoint docstring to
      describe the generalized eligibility rule.
- [x] 4.5 Update `approvals/tests.py`: add tests for delegating `stepOrder`
      0 itself, delegating a `stepOrder` 2+ step, re-delegation by the
      current delegate, rejection when the caller isn't currently
      authorized on the step, rejection when the named delegate doesn't
      meet the step's own eligibility, and a permission-denied case for a
      caller lacking `invitations:approve` entirely (per
      `testing-standards.md` §2). Also updated pre-existing tests whose
      expected status code changed under the corrected rule (host's
      blanket delegation privilege persists regardless of the current
      step's own role/delegate state), and fixed a design gap caught
      during implementation — see design.md Decision 4 — where a naive
      "delegation eligibility == acting eligibility" reuse would have
      regressed the host's original ability to delegate a role step it
      doesn't hold; both `specs/approvals/spec.md` and the implementation
      were corrected together.
- [x] 4.6 Confirm the existing `relevantToMe` delegate clause (unchanged by
      this change) still surfaces the invitation to whichever user is
      currently the delegate after a re-delegation, and add a test if one
      doesn't already cover a second/updated delegate.

## 5. Visitor and Primary Contact Profile Photo Capture

- [x] 5.1 Add `primary_contact_photo_storage_key: Mapped[str | None]` to
      `Invitation` (`invitations/models.py`) and
      `photo_storage_key: Mapped[str | None]` to `InvitationVisitor`, both
      `String(500)`, nullable; generate and apply the tenant-schema Alembic
      migration (`alembic_tenant/`, per `database-architecture.md` §5).
      Applied to the local dev tenant schema and confirmed clean.
- [x] 5.2 Add optional `primary_contact_photo_file` (single) and
      `visitor_photo_files` (list, order-matched, may be shorter than the
      visitor list) file parts to the `POST /invitations` multipart
      contract in `invitations/router.py`/`schemas.py`. Also mirrored onto
      `POST /registrations/walk-in` (`registrations/router.py`) — its
      multipart contract is declared independently at the router layer,
      not inherited automatically the way the JSON payload schema is (see
      note on task 5.6).
- [x] 5.3 Add `_validate_photo(content, max_size)` to `invitations/service.py`
      (image-only allow-list: JPEG/PNG; real content/magic-byte check, not
      content-type/extension), sized independently from the ID-proof limit
      per `file-upload-handling.md` §1 — new
      `settings.invitation_max_photo_size_bytes` (default 2 MiB), added to
      `.env.example`.
- [x] 5.4 Wire photo validation and `storage_save` calls into
      `create_invitation`'s flow, validating every supplied photo before
      persisting any file (mirroring the existing "validate all ID proofs
      before persisting any" ordering), storing the resulting keys on the
      `Invitation`/`InvitationVisitor` rows.
- [x] 5.5 Add `photoUrl` to `InvitationVisitorOut` and
      `primaryContactPhotoUrl` to `InvitationCheckInOut`/
      `InvitationDetailOut`/`InvitationTrackingOut` (not the bare
      `InvitationOut` — corrected from the original plan once its actual
      shape was inspected: it carries no other visitor-identifying field
      either, so a lone photo there would be inconsistent), resolved from
      the stored key via the existing storage-URL resolution used for
      other stored files, null when absent.
- [x] 5.6 Confirm `registrations/schemas.py` needs no change (it re-exports
      the updated types verbatim) — **correction**: `POST
      /registrations/walk-in`'s file parts are declared independently in
      `registrations/router.py` (not inherited from `invitations/router.py`
      the way the JSON schema is), so its own `UploadFile`/`File(...)`
      parameters needed the same two additions, mirrored in task 5.2.
- [x] 5.7 Update `invitations/tests.py` and `registrations/tests.py`: valid
      photo accepted and returned; omitted photo doesn't block creation;
      disguised-executable photo rejected with no invitation created;
      oversized photo rejected; PDF rejected as a photo (image-only,
      stricter than ID-proof's allow-list); group co-visitor photos are
      order-matched; walk-in inherits the same behavior.
- [x] 5.8 Update `docs/features/invitations.md` and
      `docs/features/registrations.md` describing the new optional file
      parts and size/format limits chosen.

## 6. QR Check-In/Check-Out Response Photo Display

- [x] 6.1 Add `photoUrl` to the visitor entries and
      `primaryContactPhotoUrl` to the top level of `InvitationQrCheckInOut`
      (`invitations/schemas.py`), resolved the same way as task 5.5.
- [x] 6.2 Confirm both the check-in and check-out QR endpoints (from
      Section 2) return this schema with photo fields populated. Required
      converting `_to_qr_check_in_out`/`_to_check_in_out`/`_to_tracking_out`/
      `_to_invitation_detail_out` to `async def` (resolving a storage URL is
      an awaited call) and adding `await` at each of their call sites —
      factored the shared visitor-list-with-photos construction into a new
      `_to_visitor_outs` helper to avoid repeating the photo-URL-resolution
      loop across all four.
- [x] 6.3 Update `invitations/tests.py`: QR check-in and check-out
      responses include photos when present and null when absent, for both
      the primary contact and visitor list.

## 7. Cross-Cutting Verification

- [x] 7.1 Run `ruff check` / `ruff format --check` and fix any violations
      introduced by the above. (One pre-existing unrelated formatting diff
      in an archived `openspec/changes/add-invitation-lifecycle-actions/`
      doc was left untouched — outside this change's scope.)
- [x] 7.2 Run `mypy` on `core/`, `auth/`, and any touched module handling
      PII (the new photo columns/schemas) per `project-rules.md`'s
      strict-typing scope. Found and fixed one real type-narrowing gap in
      `create_invitation`'s new photo-handling code (mypy couldn't
      correlate two independently-computed `Optional`s across a ternary);
      restructured with an explicit `if` + `assert` rather than suppressing
      the check. Full `mypy src/vmss_api` (143 files) also clean.
- [x] 7.3 Run the full `pytest` suite (`ddev exec uv run pytest`) and
      confirm green, including every permission-denied and tenant-isolation
      case added above. Two real bugs surfaced and were fixed along the
      way (not scope creep — both blocked a green suite for this change):
      (a) `factories.py`'s `InvitationFactory`/`InvitationVisitorFactory`
      didn't default the two new nullable photo-storage-key columns to
      `None`, so polyfactory's random `String` generator gave every
      factory-built invitation a bogus non-null photo URL — fixed by
      pinning both to `None`, matching the file's existing convention for
      every other optional FK/lifecycle column. (b) polyfactory's default
      `String(20)` generator for `Invitation.tracking_id` picks a uniform
      random *length* between 0 and 20, so ~5% of factory-built invitations
      got an empty tracking_id — harmless for tests comparing it for
      equality, but this change made `tracking_id` load-bearing in a URL
      path (the new canonical check-in endpoint), turning that into an
      intermittent 404 across many tests; fixed with `Use(lambda: f"INV-
      {token_hex(4).upper()}")` on the factory field. See `factories.py`'s
      updated module docstring for both.
- [x] 7.4 Confirm `tests/test_api_documentation.py`'s router-registration
      and camelCase-rendering checks still pass given the removed/added
      routes and schemas — green as part of the full suite run above.
- [x] 7.5 Verified via the generated OpenAPI schema (`app.openapi()`,
      equivalent to what `/docs` renders): `PATCH
      /api/v1/invitations/{invitation_id}/check-in` and `PATCH
      /admin/dashboard/upcoming-visitors` are both absent; `PATCH
      /api/v2/invitations/qr/{token}/check-out` is present, tagged
      `invitations`, alongside the existing check-in route; `POST
      /invitations` and `POST /registrations/walk-in`'s multipart schemas
      both list `primary_contact_photo_file`/`visitor_photo_files` with
      correct descriptions and, correctly, absent from `required`;
      `InvitationVisitorOut`/`InvitationCheckInOut`/`InvitationQrCheckInOut`
      render `photoUrl`/`primaryContactPhotoUrl` in camelCase. 79 total
      paths, schema generation clean.
