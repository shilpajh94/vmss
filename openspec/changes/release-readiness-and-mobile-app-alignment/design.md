## Context

The branch `feature/suggestions-fix` holds, past the last released commit:

- **VMSS_API (`f7ba135..e631583`):**
  - `d002399`: the audit's hardening and contract additions;
  - `1e2bcdc`: G38;
  - five move-only refactors (`e3fb628`, `7d87968`, `9c6e699`, `e5cdb96`, `e631583`).
  - The full suite is 1778 passed and the regression runner is 218/218.
- **VMMS_WEB (`bd887e2..90c3546`):** audit sections §0–§9, two fixes found
  by e2e, and the build wiring for the footer link settings. The e2e suite
  passes 124/124 and the device matrix 22/22.

These are the facts the review relies on. See proposal.md for why the
review is needed.

- **Ingress:** production reaches the API through Kong (`Openstack-K8.yml`).
  No manifest sets `FORWARDED_ALLOW_IPS`, so uvicorn and the app's
  `ProxyHeadersMiddleware` trust only `127.0.0.1`. Every request therefore
  arrives from the ingress pod's address, and slowapi keys every per-IP
  limit on it. The audit added three limits that ordinary staff traffic can
  reach, all keyed that way:
  - `GET /files/local/...`: 300/min;
  - email assets: 600/min;
  - `GET /form-builder/effective`: 120/min.
- **Migrations:** the two tenant migrations (`fe66e482f4c5`,
  `14319832f01f`) build indexes without `CONCURRENTLY`, so writes to
  `audit_logs` and `invitations` block while each index builds. Locally the
  tables hold 28k and 175 rows; production volume is unknown.
- **Deploy pipeline:** the API pipeline does not run tenant migrations;
  `scripts/upgrade_all_tenants.py` is a manual step.
- **Flutter app:** a separate repo we cannot read. The API docs name the
  calls it makes:
  - device registration and approval status;
  - `X-Device-Key` walk-in registration;
  - visit-info lookups;
  - `/kiosks`;
  - OTP verification and tracking;
  - tracking-ID, QR and code check-in/out;
  - staff `/auth/me` and the push device registration.

## Goals / Non-Goals

**Goals:**
- A merge verdict per change: safe, safe with a precondition, or a
  client-visible change.
- One deployment fix (the trusted ingress range) and a written release
  checklist.
- A migration guide the app developer can work from without reading the
  API code.

**Non-Goals:**
- Changing any API contract to soften a client-visible change. Each was a
  deliberate fix: G38, idempotency scoping, PII in errors, hidden kiosks.
- Turning on `PUBLIC_ENDPOINT_HARDENING` or `ENFORCE_SECRET_CHECK`.
- Implementing the app changes; that work happens in the Flutter repo.

## Decisions

### D1. Merge verdict

**Safe: no behaviour change for existing clients.**
- **Refactors:** the five move-only commits. The whole suite passes on each.
- **Additive response fields:**
  - `branchRoles[].permissionCodes` on `/auth/me`;
  - `preferredVisitDate`, `preferredVisitTime` and `currentApprovalStep`
    on invitation list items;
  - `checkInDevice`/`checkOutDevice` on the invitation detail.
- **Optional query parameters:** notification `sortBy`/`sortOrder`.
- **Deprecation headers:** `Deprecation: true` and `Link` on legacy
  anonymous calls. The flag is off, so the bodies are unchanged.
- **Secret check:** a weak `JWT_SECRET_KEY` only warns, because
  `ENFORCE_SECRET_CHECK` defaults to `false`.
- **Dockerfile:** unchanged, so `APP_ENV` still comes from each
  environment's `.env`.
- **Notification dedupe:** writes new Redis keys only.
- **Web routing and loading:** permission-based gating falls back to role
  names when codes are absent. A stale open tab reloads once on a missing
  chunk. Footer links stay hidden until their variables are set.

**Safe with a precondition.**
- **Rate limits behind the ingress:** the new limits behind Kong (above).
  Precondition: D2.
- **Index migrations:** run them in a quiet window (D4).
- **Web board actions:** board approve/delegate depends on the new list-item
  fields, so the API must deploy first (D3). Before this release the card
  fetched each invitation's detail; now it reads the list.
- **Celery workers:** must restart onto the new code. Task names and
  signatures are unchanged, so queued messages still run.

**Client-visible changes, live on merge with no flag:**

| Endpoint | Before | After |
|---|---|---|
| `POST /invitations`, `POST /registrations/walk-in` with `registrationType: group` and no visitors (G38) | 201 | 422 "A group registration must list at least one visitor" |
| Every route with an `Idempotency-Key` header | within one feature (all invitation routes shared one namespace), the same key replayed the first response, even on another route, from another caller or with another body; a concurrent duplicate could run twice | it replays only for the same route, caller and body; another body gives 422, and a concurrent duplicate gives 409 |
| `GET /kiosks?includeHidden=true` without `kiosks:view` | hidden kiosks included | hidden kiosks omitted |
| 422 from multipart creates | `message` was pydantic's raw text, input values included | `message` is `Invalid request: <field>: <reason>; …`, plus `errors: [{field, message}]` and no input values |
| Multipart requests | unbounded | 413 above 160 MiB or 100 files |
| `/files`, email assets, `/form-builder/effective` | unlimited | 300, 600 and 120 per minute per client |

**Client-visible later, when `PUBLIC_ENDPOINT_HARDENING` is turned on:**
- `GET /auth/employees` without `employees:view`: fields reduced to `id`,
  `fullName`, `designation`, `departmentId` and `avatarUrl`.
- `GET /kiosks` and `GET /kiosks/{id}` without `kiosks:view`: 401.
- `GET /invitations/track?email=` without a proof token for that email:
  401.
- `PATCH /api/v2/invitations/{trackingId}/check-in` without an approved
  `device-id` or a staff token holding `invitations:checkin`: 401.
- `GET /hosts/search` without `X-Device-Key`: `email` is `null`.

### D2. Trust the ingress range

Set `FORWARDED_ALLOW_IPS` to the ingress pod CIDR in each environment:
- PROD: the Kong namespace's pod CIDR;
- DEV/STAGE: their ingress or nginx range.

**Alternatives considered:**
- **`*`.** Safe only if the API pod is unreachable except through the
  ingress. Acceptable as a temporary value if the CIDR isn't known, with a
  NetworkPolicy restricting ingress to the pod.
- **Removing the three new limits.** This undoes a reviewed hardening.
  Keep it only as a fallback if D2 can't land with the merge, and then via
  config rather than a code revert.

The setting already exists (`core/config.py`) and is read by both uvicorn
and `ProxyHeadersMiddleware`, so this is configuration only.

### D3. Deploy order: API, then web, then app

The web portal reads the new list-item fields, and the app's strict-mode
work needs the new headers to be meaningful. Rolling back the web alone is
always safe. Rolling back the API alone while the new web is live hides the
board's approval actions, so roll both back together.

### D4. Tenant migrations in a window

Run `ddev exec uv run python scripts/upgrade_all_tenants.py`, or the
pipeline equivalent, right after the API image rolls out, during low
traffic. The code does not depend on the new indexes, so serving traffic
before they exist is correct, just slower on search and audit filters.
`pg_trgm` is created in a savepoint; if the database role can't create
extensions, the trigram indexes are skipped and logged, not failed.

### D5. The mobile migration guide

The guide lives at `docs/clients/mobile-app-migration.md`. It mirrors the
D1 tables, but it is written for the app developer and grouped by urgency:

- **A: before this API reaches production (live on merge):**
  - A1. Group walk-in or registration with no visitors gets 422. Validate
    at least one co-visitor (or a filled visitor-group instance) in the app
    before submitting, and show the API's message.
  - A2. Idempotency keys:
    - create one UUID per user action and reuse it only to retry the
      identical request;
    - never reuse a key for a different request or another endpoint;
    - on 409, wait and retry with the same key;
    - on 422 "Idempotency-Key reused…", generate a new key.
    - The affected calls are QR/code/tracking-ID check-in and check-out,
      invitation create, walk-in registration, OTP request and verify,
      check-out by id, and badge.
  - A3. 422 handling: read `errors[]` (`field`, `message`) for inline field
    errors, or show `message`. Stop parsing pydantic's old raw text.
  - A4. Handle 413 (upload too large) and 429 (rate limited) with a
    user-facing message and back-off; never retry 429 immediately.
  - A5. `GET /kiosks?includeHidden=true` returns hidden kiosks only to a
    caller with `kiosks:view`. If the app needs hidden kiosks, call it with
    a staff token.
- **B: before strict mode (target 2026-12-31):**
  - B1. Send `device-id` (an approved device) on every tracking-ID
    check-in. Staff flows send the staff bearer token instead.
  - B2. For tracking by email, run OTP request then verify, and send
    `Authorization: Bearer <proofToken>` on
    `GET /invitations/track?email=`.
  - B3. Send `X-Device-Key` on `GET /hosts/search` (and the other
    visit-info lookups) from the kiosk.
  - B4. Call `GET /auth/employees` with the staff token. A kiosk host
    picker should use `/auth/employees/directory`.
  - B5. Call `/kiosks` with a staff token holding `kiosks:view`.
  - B6. Log any response carrying `Deprecation: true` in debug builds, so a
    missed call shows up before the flag flips.
- **C: recommended (new fields and consistency):**
  - C1. Gate staff UI on `/auth/me` `branchRoles[].permissionCodes` instead
    of role names; tenants can define custom roles.
  - C2. Show the approval step and visit date and time from the list items
    directly, instead of fetching each invitation's detail.
  - C3. Show `checkInDevice`/`checkOutDevice` on the visit detail.
  - C4. Submit the purpose of visit as its display label ("Business
    Meeting"), and show legacy slugs (`business-meeting`) as labels.
  - C5. Treat the company `defaultTimezone` as an IANA name
    (`Asia/Kolkata`). Legacy `GMT+05:30` values may still appear.
  - C6. Cache `GET /form-builder/effective` per branch for the session
    (120/min limit).
  - C7. Map tracking statuses `submitted`, `approved`, `denied`,
    `checked_in`, `checked_out` and `archived`. Show an unknown value as is
    in a neutral style.

## Risks / Trade-offs

- **[Risk]** D2 can't land with the merge (the CIDR is unknown) →
  Mitigation:
  - set `FORWARDED_ALLOW_IPS=*` with a NetworkPolicy allowing only the
    ingress;
  - or ship with `RATE_LIMIT_ENABLED` left as is and watch for 429s on
    `/files` in the first hour, ready to raise those three limits through
    config.
- **[Risk]** The store version of the app reuses idempotency keys across
  actions, which now return 422 instead of a silently wrong replay →
  Mitigation: guide item A2 ships in the app before the API reaches PROD.
  Until then, PROD stays on the previous API image.
- **[Risk]** A large production `invitations` table makes the GIN index
  build slow → Mitigation: run D4 in the window and check the size first
  (`SELECT count(*) FROM <schema>.invitations`).
- **[Trade-off]** The guide is written against API behaviour, not the app's
  code. Items that don't apply to the app are marked "if used" rather than
  guessed at.

## Migration Plan

1. Agree the ingress CIDR with ops. Set `FORWARDED_ALLOW_IPS` in the DEV
   and STAGE variable groups and the PROD secret.
2. Hand the migration guide to the app developer, who confirms items A1–A5
   (or that they don't apply).
3. Deploy the API to DEV, then run the tenant upgrade. Deploy the web to
   DEV. Run the QA runner and the e2e smoke against DEV.
4. Repeat for STAGE, then the app's test build against STAGE.
5. PROD: deploy the API in the window, run the tenant upgrade, restart the
   workers, deploy the web.
6. **Rollback:** redeploy the previous web and API images together. The
   migrations only add indexes, so they need no downgrade to roll back.
7. Strict mode, later: after the app release with items B1–B6 has reached
   its users, enable `PUBLIC_ENDPOINT_HARDENING` in STAGE, then in PROD.

## Open Questions

- Who will run the tenant upgrade on each environment, and through which
  pipeline step? This doesn't change the plan, only who does step 3.
- Whether the app uses `/kiosks?includeHidden=true` or anonymous
  `/auth/employees` at all. The guide marks both "if used".
