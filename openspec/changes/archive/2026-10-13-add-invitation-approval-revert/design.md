## Context

`Invitation.status` is a string-valued state machine. Every transition is a
single conditional `UPDATE ... WHERE status = <expected> RETURNING`, wrapped
in a repository method: `approve_if_submitted`, `deny_if_submitted`,
`check_in_if_eligible`. The service turns a `None` result into a 409, and
notifications are dispatched only after commit.

Approval takes one of two paths:

- **Direct**: `POST /invitations/{id}/approve`, or auto-approve at creation,
  for invitations with no `InvitationApprovalStep` rows.
- **Step-by-step**: `approvals.service.approve_step`. When the last step is
  approved, it calls `invitations.service.approve_invitation` verbatim.

On the first approval, `approve_invitation` also:

- overwrites `expires_at` with the end of the visit day;
- issues the invitation's single `InvitationQRCode` (a get-or-create keyed
  by invitation);
- enqueues `send_approval_notification`;
- sends the host a push.

Every check-in path (QR, staff, public tracking-ID) gates on `status IN
(approved, checked_in, checked_out)` together with `check_in_status`, inside
its atomic `UPDATE`. A `submitted` invitation therefore can never be
admitted, whatever QR it carries.

## Goals / Non-Goals

**Goals:**
- Reuse the existing transition shape (a conditional `UPDATE`, then 409 on
  `None`, then commit, then dispatch) so revert behaves like approve and
  deny under concurrency.
- Have re-approval after a revert go through the *unchanged* approve paths.
  There is no "re-approve" endpoint.

**Non-Goals:**
- Reverting a denial, or reverting after the visitor has entered. Both stay
  out of scope; the second is a check-out concern.
- Rotating the QR token on revert (see Decision 3).
- Undoing a single workflow step while leaving the invitation approved.
- Exposing per-user action capabilities (an `availableActions` field) to
  clients. The web keeps relying on the API's 403 (see the companion web
  change).

## Decisions

### 1. Target state is `submitted`, not a new `approval_reverted` status
Revert writes `status='submitted'` and clears `approved_at`. The approve and
deny endpoints, the board's "requested" column, the `?status=` filter and
`InvitationStatus` all already treat `submitted` as "awaiting a decision",
so none of them change. The fact that a revert happened lives in three new
nullable columns:

- `approval_reverted_at`
- `approval_reverted_by_user_id` (an FK to `users`)
- `approval_revert_reason` (`String(500)`, matching `denial_reason`)

They are exposed on `InvitationOut` and `InvitationDetailOut`.

*Alternative*: a distinct `reverted` status. Rejected because every gate
that accepts `submitted` (approve, deny, step actions, list filters, web
column mapping) would need to accept it too, and it would be a new
`InvitationStatus` value that existing clients don't know how to render.
Only the latest revert is stored on the row. The full history is in
`audit_logs` (one `invitation_approval_reverted` entry per revert), which is
the system's record anyway.

### 2. Eligibility: `status='approved' AND check_in_status='unused'`, in one `UPDATE`
`InvitationRepository.revert_approval_if_eligible(id_, *, user_id, reason)`
runs a single conditional `UPDATE` whose `WHERE` checks both conditions,
mirroring `approve_if_submitted`. The `check_in_status` clause is
defensive: `checked_in` and `checked_out` statuses already exclude
admitted visitors, but the two columns are written by different paths, and
the atomic `WHERE` is the only place a race can be closed.

The service does a cheap pre-read so it can return 409 with a specific
detail message ("already checked in" vs. "not approved"). The `UPDATE`
remains the source of truth.

### 3. Keep the QR row; don't rotate the token
The QR token is `encrypt_invitation_token(invitation.id)` and
`_issue_qr_code` is a get-or-create. On re-approval `approve_invitation`
calls it again, gets the existing row back, and re-sends the same pass,
which the spec requires. While reverted, the status gate already refuses
admission, so the pass is inert without any token bookkeeping.

*Alternative*: delete the QR row so re-approval mints a new token. Rejected
for two reasons:
1. It doesn't revoke anything. Admission is gated on status, not on token
   freshness.
2. It would turn an emailed pass into a dead one, and orphan the stored QR
   image.

If "wrong visitor approved" ever needs a hard token revocation, that is a
token-versioning change in its own right.

### 4. `expires_at` is left untouched
Revert doesn't rewind `expires_at`. Re-approval recomputes it from
`preferred_visit_date` as it always does. The value set by the first
approval is a later-or-equal bound than the creation-time TTL, so keeping
it can't expire a reverted request prematurely.

### 5. Workflow reset lives in `approvals/`, called from `invitations.service`
`invitations.service.revert_invitation_approval` performs the invitation
`UPDATE` and then, in the same session and before commit, calls the
approvals side:

- `InvitationApprovalStepRepository.reset_all_for_invitation(invitation_id)`
  issues a single bulk `UPDATE` (`query-performance.md` §3) over the
  invitation's non-deleted steps. It sets `status='pending'` and nulls
  `acted_by_user_id`, `acted_at`, `delegated_to_user_id`,
  `delegated_by_user_id`, `delegated_at`, `escalates_at` and
  `auto_approves_at`.
- `InvitationApprovalStepRepository.activate_current_pending(invitation_id)`
  then sets the step-1 clock. It holds exactly the "a step becomes current
  now" logic that used to live in `approvals.service._activate_next_step`,
  which now delegates to it. It lives on the repository, not on
  `approvals.service`, because `approvals.service` already imports
  `invitations.service`, so calling back the other way would be an import
  cycle.

After commit, the service sends `step_awaiting_approval` to the activated
step's approver via `notifications_service.notify_step_approver`, which is
the same call `approve_step` makes.

`invitations.service → approvals.repository` is an existing import
direction (`approve_invitation` already uses
`InvitationApprovalStepRepository`), so no new cycle is introduced.

Reset covers `approved`, `auto_approved` and `skipped` steps. Nothing writes
the latter two today (escalation and auto-approve aren't enforced), so
treating them like `approved` is the only coherent rule and costs nothing
now. `rejected` can't occur on an approved invitation.

The invitation's `host_id` is **not** reset, even if a delegation set it.
The host is a fact about who the visitor is seeing, not an approval
decision. Resetting it would also silently drop the host push for the
revert itself.

### 6. New permission instead of reusing `invitations:approve`
The new code is `invitations:revert-approval`. Branch authorization uses
the same `authorize_branch_id_tolerant(..., invitation.branch_id)` as
approve and deny, so a soft-deleted branch still authorizes.

The permission is added to `PERMISSION_CODES` and to the `reception` and
`host` entries of `ROLE_PERMISSIONS`. `admin` picks it up automatically.

Two `alembic_tenant` revisions, following `787f2f641092` and `bff38dfa42e7`:
- `bc9c5b3c20b6` adds the three columns, using `op.add_column(...,
  schema=<target>)` because `add_column` ignores `schema_translate_map`,
  plus an FK with explicit `source_schema`/`referent_schema`.
- `6054f5200ed1` idempotently inserts the global catalog row and grants the
  permission to the standard `admin`, `reception` and `host` roles.

They're split so the grant can be tested on its own through the same direct
`upgrade()`/`downgrade()` harness `bff38dfa42e7` uses. The test schema is
built by `create_all`, so a combined revision's `add_column` would fail
there.

Downgrading both removes the grants and drops the columns, and leaves the
catalog row.

### 7. HTTP shape: `PATCH /invitations/{id}/revert-approval`, body `{reason}`
This mirrors `PATCH /{id}/deny` (`InvitationDenyRequest`). It gets a new
`InvitationRevertApprovalRequest(CamelModel)` with `reason:
Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
max_length=500)]`.

There is no `Idempotency-Key`. The conditional `UPDATE` already makes a
retried revert a harmless 409, and this is a desk action, not a flaky-
network mobile flow (`api-conventions.md` §3's list).

The audit log is written via `background_tasks.add_task(record_audit_log,
...)`, as approve and deny already do. Its action is
`invitation_approval_reverted`, with `diff={"status": {"before":
"approved", "after": "submitted"}, "reason": <reason>}`, so the history of
repeated reverts keeps every reason even though the row keeps only the
latest one.

### 8. Notifications
- **Visitor**: a new Celery task, `send_approval_revert_notification(request_id,
  tenant_schema, invitation_id)`, in `invitations/tasks.py`. It reuses
  `_RETRY_KWARGS` and the same tenant-session and request-id rebinding
  pattern as `send_denial_notification`, plus a new email template.
  - Idempotency (`background-jobs.md` §2): the task re-reads the invitation
    and sends only if it is still `submitted` and `approval_reverted_at` is
    set. A redelivery after a quick re-approval doesn't send a stale "your
    approval was withdrawn".
  - The withdrawal reason is **not** included in the visitor email or SMS.
    This differs from the denial notification, which does show the denial
    reason. A revert reason is typically an internal note ("approved the
    wrong person", "pending background check") that isn't addressed to the
    visitor. The notice says only that the approval was withdrawn, that the
    pass won't work until the request is reviewed again, and gives the
    tracking ID.
- **Host**: `push_notifications.approval_reverted(invitation)` via the
  existing `_notify_host`.

## Risks / Trade-offs

- **[Risk]** A visitor reads the original approval email and turns up anyway.
  → The pass is refused at every check-in path. They also get the withdrawal
  email, and reception sees the request back in Requested with the revert
  reason in Visitor Info.
- **[Risk]** A Celery redelivery sends the withdrawal email after the
  invitation has already been re-approved. → The task's state check
  (Decision 8) skips it.
- **[Risk]** Reverting a multi-step invitation re-notifies a step-1 approver
  who already approved. → Intended, since they must approve again. The push
  copy is the existing "awaiting approval" message.
- **[Trade-off]** Only the latest revert's actor and reason are on the row.
  → Earlier ones are in `audit_logs`.
- **[Risk]** The new tenant migrations fork `alembic_tenant` heads. → Run
  `alembic -c alembic_tenant.ini heads` before the PR. `down_revision` must
  be the current single head (`bff38dfa42e7` at time of writing; re-check).
- **[Risk]** The `vmss_test` DB has a stale schema after the new columns
  are added. → Drop `vmss_test` before running tests (known gotcha).

## Migration Plan

1. Deploy the API with the new tenant migration. The prestart and "upgrade
   all tenants" flow applies it to every tenant schema. It is additive
   (nullable columns plus grants), so it's safe to run ahead of the web
   release.
2. Ship the VMMS_WEB companion change. Until then the endpoint is simply
   unused.
3. **Rollback**: downgrade both tenant revisions. That drops the 3 columns
   and the grants. The global catalog row stays, which is harmless. Any
   invitation that was mid-revert stays `submitted` and can still be
   approved or denied normally.

## Open Questions

- Exact email subject and body copy for the withdrawal notice. This can be
  settled in review without changing the behavior.
