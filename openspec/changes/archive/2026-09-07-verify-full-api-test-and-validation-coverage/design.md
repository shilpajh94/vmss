## Context

See `proposal.md` — Why for the audit's evidence (707/707 tests passing,
clean `ruff`/`mypy`, 48 concrete file:line-cited gaps across ten features).
This design covers how to close them without regressing the green baseline
or accidentally shipping a breaking change under `skip_specs: true`.

The audit ran as four parallel investigations (test-coverage-by-feature ×2,
schema-validation + pagination, idempotency + rate-limiting, code-quality +
notification-workflow verification), each reading actual file content and
test bodies rather than inferring from names. Their findings are folded
directly into `proposal.md`'s "What Changes" — this design doesn't re-derive
them, it sequences and bounds the work.

## Goals / Non-Goals

**Goals:**
- Close every genuine test-coverage gap (tenant-isolation, permission-denied)
  the audit found, using this repo's established pattern: a repository-level
  isolation test via `make_tenant_schema`/`open_tenant_session`
  (`conftest.py`) for a single untested repository method, or an HTTP-level
  test when the gap is at the endpoint's own data-access path (org_structure's
  four laggard list endpoints, dashboard's check-in-by-tracking path).
- Add the 16 missing Pydantic constraints without rejecting any
  currently-valid value — bounds are chosen against the widest value already
  accepted by the test suite or a realistic production input, not an
  arbitrary round number.
- Refactor the 3 duplicated code blocks with no behavior change, verified by
  the existing (unmodified) test assertions for each affected code path
  continuing to pass.
- Add the 2 missing Mailpit round-trip tests and the 1 missing
  `notify_role_at_branch` unit test, matching the existing evidence bar
  (`test_send_approval_notification_delivers_email_with_qr_via_mailpit`, the
  `notify_step_approver_*` test style).
- Resolve each of the 4 list-endpoint convention findings as either a
  verified non-breaking fix or an explicit, reported follow-up — never guess.
- End with a green full suite, clean `ruff`/`ruff format --check`/`mypy`
  (scoped per `project-rules.md`: `core`, plus any newly-touched module
  handling auth/PII), and a closing summary enumerating what was fixed vs.
  deferred.

**Non-Goals:**
- Not re-running or re-deriving the API-01..API-19 stage matrix, the
  notification dual-channel work, or the QR-security hardening — those are
  already closed by the two prior archived audits and this change's own
  investigation re-confirmed (not re-derived) that OTP and QR check-in are
  fully verified with no gap.
- Not building a generic cross-feature test-fixture abstraction for
  tenant-isolation tests beyond what `conftest.py` already provides — each
  gap closes with the same `make_tenant_schema`/`open_tenant_session` idiom
  already used ~30 times in this suite.
- Not shipping any `/api/v2` breaking-change fix as part of this change —
  if a list-endpoint fix turns out to require one (pagination envelope
  change, filter-type tightening that would reject a value a real client
  currently sends), it is reported as a follow-up proposal, not implemented
  here.
- Not touching `core/emailing.py`/`identity_verification/senders.py`'s
  `SmtpEmailSender` duplication — a prior design's documented, deliberate
  choice, out of scope for a re-litigation here.

## Decisions

### Decision 1 — Tenant-isolation gaps close at the repository layer by default

For the 26 tenant-isolation gaps across `auth` (10), `invitations` (9),
`visitors` (4), `dashboard` (2), and `org_structure`'s 4-endpoint asymmetry:
default to a repository-level test (`<Repo>(other_session).<method>(...)
is None` or empty, matching the existing pattern for every already-covered
method in these files) unless the gap is specifically about an endpoint's
own resolution path not reaching the repository at all — that's true only
for `dashboard::PATCH /upcoming-visitors` (goes through
`invitations_service.check_in_invitation` directly, not
`DashboardRepository`) and `org_structure`'s four list endpoints (need an
HTTP-level test through `public_tenant_db`, matching the existing
`test_list_branches_tenant_isolation`/`test_list_departments_tenant_isolation`
pattern, since the gap is specifically that no test drives the public
listing's own tenant-resolution dependency).

Alternative considered: write every gap as an HTTP-level test for
uniformity. Rejected — the existing suite's own convention already
mixes both levels deliberately (e.g. `auth/tests.py:117`'s repository-level
`test_tenant_schema_isolation` plus `auth/tests.py:734`'s endpoint-level
`test_create_employee_tenant_schema_isolation`), and matching each gap to
its nearest existing sibling test keeps the diff minimal and consistent
with what a reviewer already expects in that file.

### Decision 2 — Validation bounds: read before writing

For each of the 16 fields, before adding a `Field(max_length=...)`/
`ge`/`le`, check: (a) the widest value any existing test in that feature's
`tests.py` already sends for that field, and (b) whether the field maps to
a DB column with its own length limit (`models.py`) that already caps it
structurally. Set the Pydantic bound to comfortably exceed (a) and match or
exceed (b) — e.g. a `String(500)` column backing a field gets
`max_length=500`, not an arbitrary smaller number. For `password` fields
(no DB column — Argon2-hashed before storage), bound generously against
NIST/OWASP guidance (e.g. 128 chars) purely to stop a pathological payload
from reaching the hashing step, not to restrict legitimate passphrases.

Alternative considered: pick a single house-style default (e.g. 255
everywhere). Rejected — `org_structure`'s `floor_number`/`capacity` are
integers needing `ge`/`le` bounds tied to physically plausible values
(e.g. a building doesn't have 50,000 floors), not a string-length default,
so a one-size rule doesn't fit the actual field types found.

### Decision 3 — List-endpoint fixes: non-breaking only, else report

Apply `api-conventions.md` §2's breaking-change test to each of the 4
findings before touching a router:
- `auth::list_permissions`, `sso::list_role_mappings`,
  `platform::list_tenants` — adding pagination wraps today's flat
  `data: [...]` in `{data: [...], pagination: {...}}`. This changes the
  response shape for existing clients — **breaking** per `api-conventions.md`
  §2. Not fixed in `v1` here; each becomes a named follow-up item in the
  closing summary (a `/api/v2` variant, or, for `list_permissions`
  specifically, confirm with the product owner whether an unpaginated
  catalog is an accepted permanent exception given its size is bounded by
  the RBAC permission set, not tenant data growth).
- `invitations::list_invitations`'s `status` filter — introducing a
  `Literal`/enum where a raw `str` was accepted before is "tightening
  validation on an existing param," also breaking per the same rule, **if**
  any currently-accepted value wouldn't validate against the enum. Resolve
  by first enumerating every value `Invitation.status` can actually hold
  (from `models.py`/`service.py`'s own state-machine writes) and confirming
  the enum is a lossless closed set matching it exactly — if so, this is a
  same-class fix as the precedent's "behavior now matches its own
  already-intended contract," not a real behavior change, and can ship
  directly. If any legacy/unexpected value is found in use, stop and report
  instead of coercing data.
- The 3 missing-sort findings (`list_employee_directory`, `list_tenants`,
  `list_role_mappings`) are purely additive (a new optional `sort_by` query
  param) — safe to add regardless of the pagination question, since an
  additive optional param is explicitly non-breaking per `api-conventions.md`
  §2.

### Decision 4 — Duplication refactors are behavior-preserving by construction

Each of the 3 refactors (invitations host-push helper, org_structure CRUD
skeleton, org_structure branch-authorization helper) is scoped to pure
extraction — the same conditional branches, same exception types, same
return values, just deduplicated. Verification is the existing test suite
for each affected file passing unchanged after the refactor, not new tests
written to prove no-behavior-change (the existing coverage already exercises
every branch being extracted, per the coverage-gap audit finding no gap in
these specific paths).

## Risks / Trade-offs

- **[Risk]** A validation bound chosen too tight silently starts rejecting a
  real (if unusual) value in staging/prod. → **Mitigation**: Decision 2's
  "read before writing" rule, plus running the full suite after each
  schema change before moving to the next — a bound that breaks an existing
  test is caught immediately, not after several changes have stacked up.
- **[Risk]** The `org_structure` CRUD-skeleton extraction accidentally
  drops one entity's unique per-entity validation hook (e.g. a
  branch/floor cross-check one entity has that another doesn't). →
  **Mitigation**: extract only the parts genuinely identical across all
  five entities (fetch/404-masks-403, uniqueness recheck, exclude-unset
  field loop, commit-or-conflict, soft-delete); leave each entity's unique
  hook as a callback/parameter rather than trying to force it into the
  shared skeleton.
- **[Risk]** Fixing `invitations::list_invitations`'s status filter turns
  out to reject a value some already-running client depends on. →
  **Mitigation**: Decision 3's explicit enumerate-and-compare step before
  changing the schema; stop and report rather than ship if the sets don't
  match exactly.
- **[Trade-off]** This change intentionally leaves 3 list endpoints
  unpaginated (Decision 3) rather than "fully closing" every finding —
  accepted because shipping a silent breaking change to `v1` clients (the
  React portal and Flutter app, on separate release cadences per
  `api-conventions.md` §2) is worse than a known, reported gap.

## Migration Plan

No data migration. Deploy as a normal code change: land the test additions
and refactors, confirm the full suite stays green, merge per
`git-workflow.md`'s normal CI gate. No rollback complexity beyond a normal
revert — no schema/contract changes ship.
