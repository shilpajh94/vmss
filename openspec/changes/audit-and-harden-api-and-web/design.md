## Context

This design is shared by both halves of the paired change `audit-and-harden-api-and-web`:
- the API half (this repo);
- the web half (`VMMS_WEB/openspec/changes/audit-and-harden-api-and-web/`).

It records the decisions for both repos and holds the **gap register**.

The source material is the five read-only audits run on 2026-10-20, against API
`f7ba135` and web `bd887e2`:
- API code quality;
- API gaps against the rules, specs and product PDF;
- web responsiveness;
- web motion, UI states, accessibility and performance;
- web functional gaps.

The findings are cited by area below. Each task in `tasks.md` names the
`file:line` it targets.

Constraints that shape the approach:

- **No regressions in current behaviour.** The user asked for "optimisations
  or refactoring without affecting the current functionalities". Every
  external change is additive, or sits behind a default-off flag.
- **The API test suite is not green today.** QA findings T1–T3 show about 236
  failures, so refactors have no safety net until the suite is repaired. Two
  test-environment gotchas also apply: the shared test DB and the shared
  Redis rate limits.
- **Three external clients:** the React web, the Flutter app and the kiosks.
  The web and API ship together in this change; Flutter and the kiosks do
  not.
- **The web's own refactor proposal is stale.**
  `optimize-web-code-reuse-and-performance` has 0/44 tasks done, and about
  half of its claims no longer match the code.

## Goals / Non-Goals

**Goals:**
- Fix every confirmed correctness bug and data-integrity risk the audits found.
- Bring the code back in line with `.claude/rules/*`.
- Remove the per-request and per-poll waste that will hurt at real tenant
  volume.
- Make every web page meet the existing `responsive-layout`, `ui-motion` and
  `async-ui-states` specs, plus a new accessibility baseline.
- Leave a prioritised, actionable register of what is still missing.

**Non-Goals:**
- Building missing product features. Blacklist, overstay, cancel, recurring
  invites, holiday calendar, token refresh, the security-role UI and the rest
  all go to the gap register.
- Any **breaking** API change, including fixes that change a status code or
  remove a field. These are registered with a proposed deprecation path.
- Visual redesign. Any spacing, colour or motion change is limited to what a
  spec or WCAG AA requires.

## Decisions

### D1. Phasing: a safety net first, then behaviour-preserving work

The order is:
1. P0 bugs.
2. P4 test repair. It is the precondition for refactors, so it is scheduled
   early despite its number.
3. P1 security and contract work.
4. P2 performance.
5. P3 refactors (the large module splits go last).

Each phase is its own commit or PR group, so a regression bisects to one
phase.

*Alternative:* one big-bang PR. Rejected, because nobody could review it and
nothing could be rolled back.

### D2. Revert notification: fix the call, add a template, fall back to email

`send_approval_revert_notification` passes `sms_body=` to a `_dispatch` that
requires `sms_template` and `sms_variables`.

The fix:
- Add `SmsTemplate.approval_reverted`, with its DLT/WhatsApp template-id
  settings.
- When that template id is blank, which is likely until Fast2SMS DLT approves
  a new template, send by email when an address exists. Otherwise skip, with
  a WARNING.

DLT template registration is an external, manual step, so it goes into the
gap register.

*Alternative:* reuse an existing SMS template. Rejected, because the DLT
wording is fixed and none of the existing templates says "withdrawn".

### D3. Idempotent notification tasks via per-recipient Redis sent markers

The key format is `vmss:{tenant_id}:notifications:sent:{event}:{entity_id}:{recipient_hash}`,
written with `SET NX` and a 7-day TTL. The task:
1. Checks the marker before sending.
2. Writes it only after the provider call succeeds.

The rollup snapshot moves its marker to after the send.

*Revised during apply.* The marker is keyed on the **Celery task id** plus
the channel and recipient hash:
`vmss:{tenant_schema}:notifications:sent:{task_id}:{channel}:{recipient_hash}`.
It is not keyed on the event and entity. A retry or broker redelivery reruns
under the same task id, and every new logical event is a new `.delay()`, so
no per-event version field is needed. A legitimate second revert of the same
invitation still notifies.

This also makes multi-recipient loops resumable, because a retry skips
recipients already reached. The planned per-recipient fan-out (task 1.6) is
therefore unnecessary and was not done.

Two further points:
- The tenant segment uses the schema name, because these tasks are enqueued
  with the schema, not the tenant id.
- If Redis is unreachable, the send still happens: a duplicate beats a lost
  notification.

*Alternative:* a DB status column per notification. Rejected because it
needs a new table and migration for every event type. Redis is already the
rule-sanctioned store for ephemeral state (`database-architecture.md` §6).

### D4. Public-endpoint hardening as deprecate-then-enforce

A single setting, `PUBLIC_ENDPOINT_HARDENING`, defaults to `false`. A shared
dependency `public_access_mode()` returns `legacy` or `strict`:

- In **legacy** mode it adds `Deprecation: true` and `Link` headers whenever
  the request lacks the strict credential.
- In **strict** mode each endpoint enforces its credential as
  `specs/public-endpoint-hardening` describes. Strict-mode responses on the
  employee list and host search use separate slim schemas
  (`PublicEmployeeOut`, `PublicHostSearchResultOut`), so the full schemas stay
  untouched.

Two changes ship unconditionally in both modes:
- **Kiosks:** `includeHidden` is ignored for anonymous callers. Hidden kiosks
  are admin-only by the spec's own definition, and no anonymous client can
  legitimately need them.
- **Docs:** the feature docs gain a dated deprecation note
  (`api-conventions.md` §2).

The web always sends a token whenever it has one (web D-W2), so turning on
strict mode never affects the web.

*Alternatives:*
- `/api/v2` copies of every endpoint. Rejected: it multiplies routes for what
  is really a credential requirement.
- Enforce immediately. Rejected by the user.

### D5. Idempotency: a scoped key plus a SET NX in-flight lock

The cache key becomes
`vmss:{tenant_id}:idempotency:{method}:{route_template}:{caller}:{key}`.
- `caller` is the user id, the device id, or `sha256(identifier)` on the
  public OTP routes.
- The cached record also stores the `sha256` of the request body. A key
  reused with a different body gets a 422.
- An in-flight marker is set with `SET NX EX 60` before execution. A
  concurrent duplicate gets a 409.

Records cached under the old key format are simply never read again; they
expire on their 24h TTL.

This tightens behaviour only for key misuse, which was never a supported
contract, so it counts as additive.

### D6. One timezone resolver in `core/timezones.py`

`resolve_timezone(name) -> tzinfo` works in this order:
1. Try `ZoneInfo` (IANA).
2. Otherwise parse `^(GMT|UTC)([+-])(\d{1,2}):?(\d{2})$` into
   `datetime.timezone(offset)`.
3. Otherwise fall back.

It replaces the two separate resolvers in `dashboard/service.py:39` and
`invitations/service.py:136`. The web switches to IANA names (web task).
Write-side validation, which would reject unknown strings, is a breaking
tightening, so it goes to the register.

### D7. Explicit loader for the current user (revised during apply)

The original plan was to switch `User.branch_roles`, `UserBranchRole.role`
and `Role.permissions` to `lazy="raise"`. The task 5.2 inventory showed that
would be a poor trade:
- `User.has_permission` walks the whole chain. It runs on every
  authenticated request, and inside approvals for users other than the
  caller, so nearly every `User` load genuinely needs it.
- `selectin` loads the chain as three batched `IN` queries per statement,
  not one query per row. On a list page the avoidable cost is about one
  permissions query.
- `raise` would turn every untested path that calls `has_permission` into a
  runtime error.

What was done instead:
- The relationship strategies are unchanged.
- `get_current_user` now loads through
  `UserRepository.get_with_permissions`, which spells the chain out with
  `selectinload`. This also fixes the layering issue the audit raised:
  `core/tenancy.py` no longer builds its own `select()`.
- `/auth/me` `permissionCodes` reads from that same loaded chain.

### D8. Long-lived S3 client for presigning

`core/storage.py` keeps a module-level aioboto3 client for each event loop,
created lazily and closed on app shutdown. Celery tasks use the same helper,
keyed by loop id, so each `asyncio.run` gets its own client, disposed at the
end of the task.

### D9. Indexes as two new tenant migrations

Two migrations, with ids generated rather than hand-typed (see the gotcha
memory):

1. **`audit_logs`:** a composite index on
   `(entity_type, entity_id, created_at DESC)` and an index on
   `actor_user_id`.
2. **Search** (`14319832f01f`): GIN trigram indexes on
   `invitations.primary_contact_full_name` and `tracking_id`.
   *Revised during apply:* the migration itself runs
   `CREATE EXTENSION IF NOT EXISTS pg_trgm` inside a savepoint. That way
   existing tenants get the extension through `upgrade_all_tenants.py`,
   with no separate provisioning step. Where the role can't create
   extensions, the migration logs a warning and skips the indexes; search
   still works, just unindexed.

Both migrations were applied locally on 2026-10-22, and `alembic heads`
returns a single head (`14319832f01f`).

### D10. Refactor boundaries

The module splits keep the public import paths stable:
- `invitations/service.py` becomes a package-style set of modules
  (`creation.py`, `checkin.py`, `edit.py`, `approval.py`, `export.py`).
  `service.py` re-exports the same names, so routers and tests don't change
  in the split commit.
- Presenters move to `invitations/presenters.py`.
- `invitations/tests.py` becomes a `tests/` subpackage, moved without
  changing any test body.

Shared helpers go to `core/`:
- `database.order_clause` and `TenantScopedRepository.sort_columns`;
- `logging.current_request_id`;
- `celery_app.DEFAULT_RETRY_KWARGS` and `run_tenant_task`;
- `responses.PaginationMeta.build`;
- `storage.url_for_optional`;
- `masking`.

The `AsyncSession` import in services is allowed **under `TYPE_CHECKING`
only**. This decision is recorded here and not as a rule change. Any runtime
use moves to a repository.

### D11. Web: permission-based gating from `/auth/me` (web half)

The web derives `can(code, branchId?)` from `branchRoles[].permissionCodes`.
It replaces the role-name checks (`staff-auth-repository.ts:30`,
`can-manage-devices.ts`, the board action visibility) and powers:
- an `AdminLayout` route guard (QA F7);
- hiding "Register visitor" for callers without `invitations:create`.

The role name is kept only for choosing the landing page.

### D12. Web: one fetch-and-poll contract

A shared `useLiveResource` (extending `useLoadTracker` and `usePageRefresh`)
follows these rules:
- Only the initial load toasts on error. A failed background poll sets
  `hasFailed` and shows the "retrying" state from `live-data-refresh`.
- Reference data (current user, option lists, roles, hosts) is fetched once
  per page mount or from context, never on every poll.
- `CurrentUserContext` is the single source of the current user.

Board card details stop being fetched once per card. The board reads
`currentApprovalStep` from the list item, which the API adds in this change
(invitations delta), loaded with one `selectinload` per page. The board
fetches the full detail only when the Visitor Info modal opens.

### D13. Web: code splitting and asset weight

- Every route group gets `React.lazy`: admin, staff, form builder and
  wizards.
- `firebase/messaging` is loaded with a dynamic `import()` after login.
- `lobby-hero.png` is converted to AVIF/WebP with a PNG fallback, and gets
  `fetchpriority="high"`.
- Target: the public landing bundle stays under 350 KB gzipped. The baseline
  is recorded in `tasks.md` before and after.

### D14. Web: accessibility baseline as a new spec

Covered: visible focus on every interactive control, AA contrast for text
tokens, labelled inputs, and no nested interactive elements.

`--color-text-faint` is darkened to meet 4.5:1 on its surfaces, and the
success text gets its own token. This is the one intentional visual change,
and it is minor.

### D15. Supersede the stale web optimisation change

The still-valid items move into the web tasks:
- `StatusBadge`;
- the route-level auth guard;
- removing the redundant current-user fetches;
- the `moveItem` dnd helper;
- the unified visitor form entry;
- `PaginationMetaSchema` adoption;
- the `DepartmentsTable` memo;
- `FormPageHeader`/`BackButton` adoption.

The stale ones are dropped. On archive, `optimize-web-code-reuse-and-performance`
is deleted, not archived. Its proposal gets a "Superseded by" note now.

## Gap register

The register lists features and tightenings that are deliberately **not**
built here. Each row is a proposed follow-up change.

Priority means:
- **P1:** an operational or security risk, or a core product-doc flow;
- **P2:** an important product-doc feature;
- **P3:** nice to have.

"Break?" says whether the change breaks an existing API contract and so
needs v2 or a deprecation path.

| # | Gap | Where | Pri | Break? | Proposed change |
|---|---|---|---|---|---|
| G1 | Token refresh flow. The refresh token is issued but never used; staff are signed out after 30 min mid-task. | API+web | P1 | no | `add-token-refresh` |
| G2 | Staff check-in, badge print/reprint, extend and watchlist override actions on the web board. The API exists for all but staff check-in. | web (+API authed check-in) | P1 | no | `add-board-visit-actions` |
| G3 | Security-role UI: gate verification, active visitors, vehicle check. | web | P1 | no | `add-security-console` |
| G4 | Blacklist/watchlist management and block visitor. `watchlist_flagged` is never set. | API+web | P1 | no | `add-visitor-blacklist` |
| G5 | Emergency "who's inside" one-click report per building, plus an export building filter. | API+web | P1 | no | `add-emergency-muster-report` |
| G6 | Cancel invitation. The `invitations:cancel` permission exists but has no endpoint and no status. | API+web | P2 | no | `add-invitation-cancel` |
| G7 | Overstay detection and alerts. | API+web | P2 | no | `add-overstay-detection` |
| G8 | Host email/SMS on visitor check-in. Push only today. | API | P2 | no | `notify-host-on-checkin` |
| G9 | Per-step auto-approve, escalation and auto-reject. The timers are computed but never act. | API+web | P2 | no | `enforce-approval-timers` |
| G10 | Recurring invitations and .ics calendar invites. | API+web | P2 | no | `add-recurring-invites` |
| G11 | Holiday calendar and enforced working hours. | API+web | P2 | no | `add-working-calendar` |
| G12 | Data-retention purge/anonymisation for visitor PII. | API | P2 | no | `add-data-retention` |
| G13 | Branding: logo upload and colours. The web logo picker is local-only. | API+web | P2 | no | `add-tenant-branding` |
| G14 | Reports by company, overstay, frequent visitors, contractor hours; peak hours beyond today; a cross-branch rollup UI. | API+web | P3 | no | `extend-reports` |
| G15 | SSO admin page (config and role mappings). The API exists. | web | P2 | no | `add-sso-admin-page` |
| G16 | Employee CSV import. The "Import Hosts" stub is removed in this change. | web | P3 | no | `add-employee-import` |
| G17 | Reception desk and security gate CRUD pages (API exists), or a spec change to "devices only". | web/spec | P3 | no | product decision |
| G18 | Badge templates and designer; badge with photo and branding. | API+web | P3 | no | `add-badge-templates` |
| G19 | Notification template admin; Teams/Slack channels. | API+web | P3 | no | `add-notification-templates` |
| G20 | Multiple languages (i18n). | web+API | P3 | no | `add-i18n` |
| G21 | Access control: zones, RFID/biometric/turnstile hooks; gate id recorded on check-in. | API | P3 | no | `add-access-control-hooks` |
| G22 | Global 422 envelope (QA F2). `RequestValidationError` keeps FastAPI's `detail[]`. | API | P1 | **yes** | v2 envelope, or a header-negotiated opt-in |
| G23 | Building/floor delete with active children returns 409 (QA F5). | API | P2 | **yes** | deprecation note, then enforce |
| G24 | Slim public `GET /branches` schema (QA F6). | API | P2 | **yes** | fold into `public-endpoint-hardening` strict mode |
| G25 | Creator visibility in `relevantToMe` (QA F3). | API | P2 | no (product decision) | extend `delegator-retains-invitation-visibility` |
| G26 | `visitor_return_visit` pagination aligned to the envelope and `pageSize`. | API | P3 | **yes** | v2 |
| G27 | Pagination for the platform tenants list and the SSO role mappings. | API | P3 | **yes** | v2 |
| G28 | Timezone write validation (reject non-IANA values). | API | P3 | **yes** | after the web ships IANA names |
| G29 | Reschedule-into-the-past guard on the API (the web min-date ships here). | API | P2 | **yes** (tightening) | deprecation, then enforce |
| G30 | Workflow level editing (`isMandatory`, escalation, auto-approve minutes) and atomic save. | web(+API) | P2 | no | with G9 |
| G31 | Multi-action audit filter (for example, every "checked in" variant); the full audit filter set in the UI. | API+web | P3 | no | `extend-audit-filters` |
| G32 | Fast2SMS DLT template registration for `approval_reverted` (D2). | ops | P2 | no | manual |
| G33 | Malware scanning on uploads (`file-upload-handling.md` §4). | API | P1 (pre-prod) | no | security-owner decision |
| G34 | Camera capture for visitor photo (`capture` attribute, live preview). | web | P3 | no | `add-photo-capture` |
| G35 | Visitor search in the top bar (`/admin/dashboard/search` exists). | web | P2 | no | `add-global-visitor-search` |
| G36 | Notification feed paging and an unread toggle. | web | P3 | no | small follow-up |
| G37 | `qr_token` carried in the Celery broker payload; QR token TTL. | API | P2 | no | `harden-qr-token` |
| G38 | **Resolved 2026-10-22.** A `group` invitation with zero co-visitors was accepted. `create_invitation` now rejects it with 422 unless `visitors` or a field group has instances (the main spec's "at least one visitor"). | API | — | no | done in this change |
| G39 | Streaming exports (`yield_per` plus incremental CSV/XLSX/PDF writers) for the invitation export and the audit report. Both are bounded today, by the 10k row cap and by running in Celery. | API | P3 | no | `stream-exports` |
| G40 | Upload cleanup: delete already-stored objects when a later save or the DB commit fails. Once that exists, upload validated files concurrently with a task group. | API | P3 | no | `invitation-upload-cleanup` |
| G41 | Cache the per-request user → role → permission load (QA L1: about 45% of CPU under load), for example a short-TTL Redis cache keyed by user id and invalidated on role or permission changes. | API | P1 (before scale-out) | no | `cache-request-permissions` |

## Risks / Trade-offs

- **[Risk, retired] D7's `lazy="raise"`.** This was dropped during apply;
  see D7 for why.
- **[Risk] The module splits produce huge diffs that hide real changes.**
  → Make each split commit move-only (re-exports, no edits). Verify with
  `git diff --color-moved` and an unchanged test count.
- **[Risk] Lazy loading (D13) adds a flash on first navigation.**
  → Use the existing `RouteTransition` fallback and a skeleton per layout,
  and prefetch the admin chunk after login.
- **[Risk] The contrast token change (D14) shifts look and feel.**
  → Darken only `text-faint` and the success text; get a before/after
  screenshot review with the user.
- **[Risk] The pg_trgm extension isn't available on the managed Postgres.**
  → Make the migration skip the GIN index with a logged notice when the
  extension can't be created. Search keeps working, just unindexed.
- **[Risk] The idempotency 409/422 surprises a client that reuses keys.**
  → The web generates a key per action already. Check the Flutter usage
  before merging and note it in `docs/features/`.
- **[Trade-off]** Strict hardening stays off by default, so the PII exposure
  remains in production until an operator turns it on. This is accepted per
  the user's decision. The `Deprecation` headers and the docs note make it
  visible.

## Migration Plan

1. The API ships first: P0, the P4 repair, then P1 (additive fields and the
   flag off), then P2 (two tenant migrations; upgrade every tenant, which
   locally means only `tenant_default`), then P3.
2. The web ships after the API's P1. It depends on `permissionCodes`, the
   list-item visit date and time, and the detail devices.
3. Operators announce the deprecation to the Flutter and kiosk teams. Once
   they confirm, they set `PUBLIC_ENDPOINT_HARDENING=true` in staging, then
   production.
4. **Rollback:** each phase reverts independently. The index migrations have
   downgrades. The flag reverts strict mode instantly.

## Open Questions

- Do the Flutter app and kiosks call `GET /auth/employees`, `/hosts/search`
  or `/invitations/track?email=` today? This only affects when strict mode
  can be turned on, not this change's tasks.
- Is `pg_trgm` permitted on the eventual production Postgres? The deployment
  target is still undecided (`project-rules.md`). The fallback in Risks
  covers both outcomes.
