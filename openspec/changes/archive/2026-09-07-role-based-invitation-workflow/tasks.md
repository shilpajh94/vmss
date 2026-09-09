## 1. Default Host Role Configuration

- [x] 1.1 Add a tenant-level "default host role" setting (nullable FK to
      `Role`, resolving to the tenant's `reception` role when unset) and a
      migration for it (`alembic_tenant/`, since it's tenant-scoped
      configuration)
- [x] 1.2 Add one resolver function (e.g. `get_default_host_role(tenant_db)`)
      used by every place that needs "the owning role" — no repeated string
      literals for `"reception"`

## 2. Ownership Step Becomes Unconditional and Role-Identified

- [x] 2.1 Update `approvals` snapshot logic (`_build_approval_steps` or
      equivalent in `invitations/service.py`) to always create `stepOrder`
      0 role-identified for the resolved default host role, regardless of
      category rule count, instead of the current host-resolved-at-creation
      conditional
- [x] 2.2 Remove the client-side `hostId`/`hostNameOrEmail` resolution path
      from invitation/walk-in creation (`_resolve_visit_detail_ids`) —
      accept-but-ignore both fields per the spec (don't reject, to avoid
      breaking un-updated clients outright)
- [x] 2.3 Unit/integration tests: a category with N active rules snapshots
      N+1 steps (0 plus N); a category with zero rules still snapshots
      exactly one (`stepOrder` 0) step; a submitted `hostId`/
      `hostNameOrEmail` is silently ignored and the invitation still creates
      successfully

## 3. Delegation Resolves the Host

- [x] 3.1 Relax `delegate_step`'s named-delegate eligibility check: when the
      step being delegated is `stepOrder` 0, require only
      `invitations:approve` at the branch, not the step's `approverRoleId`
      role — every other step's eligibility is unchanged
- [x] 3.2 On successful delegation of `stepOrder` 0 (first delegation or
      re-delegation), set `Invitation.host_id`/`host_name_or_email` to the
      delegate in the same transaction
- [x] 3.3 Dispatch push + email to the newly assigned host on delegation of
      `stepOrder` 0 (new — delegation dispatches nothing today); no
      dispatch when a later step is delegated
- [x] 3.4 Update `relevantToMe`'s clause (a) to key off `Invitation.host_id`
      directly rather than "the `stepOrder` 0 host-identified step's
      `approverUserId`" (the literal condition that no longer applies to
      new invitations)
- [x] 3.5 Tests: a reception-role holder delegates `stepOrder` 0 to someone
      who does not hold the reception role, and it succeeds; delegating a
      later configured-chain step still requires the named delegate to hold
      that step's role; delegating `stepOrder` 0 sets `hostId` and notifies
      the delegate; re-delegating updates `hostId` again and notifies the
      new delegate only

## 4. Edit Invitation Endpoint

- [x] 4.1 Add `invitations:edit` permission to the catalog
      (`auth/rbac_catalog.py`), granted to `reception` (and any other role
      that should have it — confirm against the standard role permission
      table)
- [x] 4.2 Add `PATCH /invitations/{id}/edit` — request schema covering
      `purposeOfVisit`/`purposeId`, `preferredVisitDate`,
      `preferredVisitTime`, `expectedDuration`/`durationId`,
      `departmentToVisit`/`departmentId`, `additionalNotes` (no separate
      location/building column exists on `Invitation` to edit — dropped
      from scope, `departmentToVisit` is the closest real field); explicitly
      rejects `hostId`/`hostNameOrEmail`, visitor-personal fields, and
      `visitorCategoryId` with a validation error if present
      (`extra="forbid"`)
- [x] 4.3 Repository: atomic conditional-UPDATE eligible only for
      `submitted`/`approved` status, following the existing
      `reschedule_if_eligible`/`extend_if_eligible` pattern
- [x] 4.4 Dispatch a notification to the primary contact (and the resolved
      host, if any) on successful edit, describing what changed, via the
      existing `preferredContactMethod` channel-routing rule
- [x] 4.5 Tests: happy-path multi-field edit; visitor-personal-field/
      visitorCategoryId/host-field rejection; ineligible-status 409;
      missing-permission 403; unknown-id 404; notification dispatched to
      primary contact and (when resolved) host

## 5. Email Templating System

- [x] 5.1 Add `jinja2` dependency (`uv add jinja2`)
- [x] 5.2 Build the base HTML layout template (logo, header/footer, brand
      color) plus per-notification-type content blocks (creation/tracking,
      submission-to-owning-role, host-assignment, approval, denial,
      reschedule, edit)
- [x] 5.3 Extend `EmailSender.send()` (or add a rendering helper in front of
      it) to accept a rendered `(subject, html_body, text_body)` and send
      multipart; update every call site in `invitations/tasks.py` to render
      through templates instead of building f-strings
- [x] 5.4 Implement the rendering-failure fallback: log at `ERROR` with
      notification type + invitation id, send a minimal plain-text email
      instead of failing silently
- [x] 5.5 Rewrite the approval email content to include tracking ID, visit
      date/time, duration, location/building/department, purpose, and the
      resolved host's name + a contact channel — falling back to the
      branch's front-desk contact when no host is resolved yet
- [x] 5.6 Tests: each notification type renders without error given a
      representative context; a forced rendering failure falls back to
      plain text and logs at `ERROR`; approval email contains host contact
      info when resolved, and branch contact info when not; no sensitive
      field (ID-proof number, OTP) appears in any rendered template

## 6. Owning-Role Email Fan-Out and Push Payload Metadata

- [x] 6.1 Add a role-fan-out email primitive (parallel to
      `notify_role_at_branch`'s push version) that resolves full `User` rows
      (for `.email`) for every holder of a role at a branch, skipping users
      with no usable email
- [x] 6.2 Dispatch the new "submission notifies the owning role via email"
      notification alongside the existing push dispatch at submission
- [x] 6.3 Add `assignedRoleId`/`assignedUserId`/`reason` fields to every
      invitation-related push payload, populated consistently by whichever
      dispatch primitive sent it (role-fan-out vs. specific-user)
- [x] 6.4 Tests: submission emails every role-holder with a usable email and
      skips those without one, without failing the request; push payloads
      carry the correct addressing metadata for both role-fan-out and
      specific-user dispatches

## 7. Cleanup and Cross-Cutting

- [x] 7.1 Remove the now-dead "Invitation Creation Notifies the Resolved
      Host via Email" code path (host never resolves at creation anymore)
- [x] 7.2 Update `docs/features/invitations.md` (and
      `docs/features/approvals.md`/`notifications.md` if they exist) to
      describe the new ownership/delegation/email-template behavior, per
      `project-rules.md`'s "add a short markdown file under docs/features/"
      expectation
- [x] 7.3 Run full `pytest` suite; confirm no existing test asserts the
      now-removed host-identified-at-creation behavior without being
      deliberately updated — 820/820 passing, including two pre-existing
      cross-feature E2E tests (`tests/test_workflow_full_lifecycle.py`,
      `tests/test_workflow_visitor.py`) updated for the new host-resolution
      flow
- [x] 7.4 Confirm `ruff check`/`ruff format --check` clean and `mypy` clean
      on every touched module under `core/`, `auth/`, or handling PII (per
      `project-rules.md`'s strict-typing scope) — clean across the whole
      `src/` tree
