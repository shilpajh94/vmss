## Context

See `proposal.md` - Why for motivation. Relevant current state:

- `role-based-invitation-workflow` is archived on the API side (all 26 tasks
  done); its `VMMS_WEB` twin is 26/27 done, blocked only on an unperformed
  manual E2E pass (task 7.2).
- All three invitation-creation channels funnel through one service function
  (`invitations/service.py::create_invitation`): the visitor self-service
  wizard and the staff pre-registration wizard both call `POST /invitations`;
  walk-in calls `POST /registrations/walk-in`, which delegates to the same
  function. There is no separate code path per channel to verify — the
  channel differences are almost entirely on the `VMMS_WEB` side (which
  wizard renders) and in `source`/auth (authenticated staff vs. unauthenticated
  walk-in).
  A repository bug specific to one caller (e.g. a missing `selectinload` hit
  only from the walk-in code path, or a permission check only exercised by
  the staff wizard) is still possible even though the shared function is one
  code path, since each caller's surrounding context (auth dependency chain,
  request validation, calling convention) differs — that's exactly what this
  change's task list re-verifies rather than assumes.
- `VMSS_API` and `VMMS_WEB` are separate repos with independent `openspec/`
  roots and no registered shared store (`openspec store list` returns none),
  so this change's `allowedEditRoots` is `VMSS_API` only — it cannot edit or
  mark tasks done in `VMMS_WEB/openspec/changes/role-based-invitation-workflow/`.

## Goals / Non-Goals

**Goals:**
- Prove, with real Postgres-backed tests (per `testing-standards.md`), that
  role-owned creation, delegation, edit, and branded-email rendering behave
  correctly for both callers of `create_invitation` (staff pre-registration
  via `POST /invitations`, walk-in via `POST /registrations/walk-in`) — not
  only the visitor self-service caller the user already checked by hand.
- Prove the staff/admin invitation board's full action set (approve, deny,
  delegate, reschedule, extend, badge issue/reprint, check-in/out) still
  passes after `approvals/service.py` and `notifications/service.py`'s
  changes from the archived rollout.
- Prove SSO's full flow (provider config, `start_login`/`handle_callback`/
  `redeem_exchange_code`, provisioning, role mapping) is unaffected.
- Run the full lint/type/test gate (`ruff check`, `ruff format --check`,
  `mypy` scoped per `project-rules.md`, full `pytest`) to catch any
  unrelated regression.
- Produce a concrete, itemized manual-verification script that closes
  `VMMS_WEB` task 7.2 for all three channels (not just the one already
  spot-checked), for a human (or a future session with browser tooling) to
  execute against `VMMS_WEB`.

**Non-Goals:**
- Editing anything under `VMMS_WEB` — that repo's own change/task tracking
  stays there; this change only hands it a verification script.
- Building new invitation types (recurring/bulk/group invites) — confirmed
  via exploration that none are asked for or missing; "all invitation areas"
  means the existing channels/board, not new ones.
- Re-auditing everything `verify-full-api-test-and-validation-coverage`
  (2026-09-03, archived) already covered — this change is scoped to what
  `role-based-invitation-workflow` touched (invitations, approvals,
  notifications, plus SSO as an explicit ask) and a full-suite regression
  run, not a from-scratch full-API audit.

## Decisions

- **Verify by extending real tests, not by manual poking, on the API side.**
  Per `testing-standards.md`, every gap found gets a `pytest` case (endpoint-
  level via `httpx.AsyncClient` for contract/auth/status, service-level for
  business-rule edge cases) rather than a one-off manual check whose result
  isn't preserved. This matches the archived audit's own approach and means
  the regression pass leaves the suite stronger, not just "seen to pass once."
  *Alternative considered*: a manual smoke-test checklist only. Rejected —
  it wouldn't survive to catch the next regression, and the project's own
  rules (`testing-standards.md` §2) already mandate the coverage this would
  otherwise skip.
- **Treat each of the three creation callers as needing its own explicit
  test evidence**, even though they share `create_invitation`, because their
  surrounding request/auth context differs (staff-authenticated multipart
  request vs. unauthenticated walk-in vs. visitor self-service — already
  checked by the user). Concretely: confirm role-owned `stepOrder=0`
  snapshotting, `hostId`/`hostNameOrEmail`-ignored-not-rejected, and the
  branded-email dispatch all fire correctly from **both** `POST /invitations`
  (staff pre-registration) and `POST /registrations/walk-in`.
- **Board-action regression scope is the full action set the archived
  change's `Impact` section named as touched**, not a re-audit of every
  invitation endpoint: `approvals/service.py`'s delegation-eligibility
  relaxation (§3 of the archived tasks) and `notifications/service.py`'s new
  push-payload addressing fields are the two shared surfaces most likely to
  have a knock-on effect on approve/deny/reschedule/extend/badge/check-in-out,
  so those get explicit regression cases; endpoints untouched by the archived
  change get a single full-suite `pytest` run as their regression evidence,
  not new hand-written cases.
- **SSO gets a targeted re-run, not new test authorship**, since exploration
  found the only uncommitted SSO diff is one new test for an existing sort
  parameter — there's no code-behavior change to regression-test against, only
  confirmation that adding that test didn't break anything else in
  `sso/tests.py` and that the full flow still passes end to end.
- **Cross-repo coordination is a handoff document, not an edit.** Since
  `VMMS_WEB` has its own `openspec/` root outside this change's
  `allowedEditRoots`, task 7.2's channel-by-channel manual script is written
  as a `tasks.md` deliverable in *this* change (a plain checklist a human runs
  against the deployed web app), left for the user or a `VMMS_WEB`-scoped
  session to execute and then mark 7.2 done there.

## Risks / Trade-offs

- [A gap surfaces in `approvals`/`notifications` shared code that requires a
  real fix, not just a missing test] → Fix it in place (same repository-
  pattern, tenant-scoped conventions the archived change already followed)
  and add the regression test alongside, same as the precedent audit did;
  do not defer a found bug to a separate change.
- [Full-suite `pytest` takes long and something unrelated is already flaky]
  → Note pre-existing failures separately from anything this change's diff
  introduces, per the precedent audit's practice of citing a clean baseline
  before attributing a new failure to the change under review.
- [The manual web verification script sits unexecuted if no one runs it
  against `VMMS_WEB`] → This change is only complete-in-scope for the API
  side once that script exists; closing `VMMS_WEB` task 7.2 itself is
  explicitly out of this change's control and is flagged as a follow-up
  action for the user, not silently assumed done.
