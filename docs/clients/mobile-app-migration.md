# Mobile app migration guide: October 2026 API release

For the Flutter app developer. This lists every API change from the
`audit-and-harden-api-and-web` work that the app can observe, grouped by
when the app has to ship it. Every path is under `/api/v1` unless shown
otherwise.

| Group | Deadline | What happens if missed |
|---|---|---|
| **A** | Before this API reaches production | The request fails or behaves differently as soon as the API is deployed |
| **B** | Before strict mode is enabled (target 2026-12-31) | Works today, with a `Deprecation: true` header; fails once strict mode is on |
| **C** | Any release | Nothing breaks; these are new fields and consistency fixes |

Please answer each A item with "done in vX.Y" or "not used by the app".
The rollout waits for that (release checklist, section 1).

## A. Must ship before this API reaches production

### A1. A group registration needs at least one visitor
`POST /registrations/walk-in`, `POST /invitations`

- **Before:** `registrationType: "group"` with no co-visitors returned 201.
- **Now:** 422 `"A group registration must list at least one visitor"`.
  A filled visitor field-group instance (`groups[].instances`) also counts.
- **App:** check that a group has at least one co-visitor before
  submitting, and show the API's `message` if the 422 still comes back.

### A2. Idempotency keys are per request
These routes take an `Idempotency-Key` header:
- `POST /invitations`;
- `POST /registrations/walk-in`;
- `POST /identity-verification/otp/request` and `/otp/verify`;
- `PATCH /api/v2/invitations/{trackingId}/check-in`;
- `PATCH /api/v2/invitations/code/check-in` and `/code/check-out`;
- `PATCH /api/v2/invitations/qr/{token}/check-in` and `/check-out`;
- `PATCH /invitations/{id}/check-out`;
- `POST /invitations/{id}/badge`.

What changed:
- **Before:** within one area, the same key replayed the first response
  for any later request, even to another route, from another caller or
  with another body. Two simultaneous duplicates could both run.
- **Now:** a key replays only for the same route, caller and body.
  - A different body with a used key returns **422**.
  - A duplicate sent while the first is still running returns **409**.
  - A failed attempt frees its key, so a retry with the same key runs.

What the app does:
- Generate one UUID per user action, for example one tap on "Check in".
- Reuse that key only to retry the identical request after a timeout or
  network error.
- Never reuse a key for another visitor, endpoint or payload.
- On **409**, wait about a second and retry with the same key.
- On an idempotency **422**, treat it as a new action with a new key.

### A3. Validation errors have a new format
Any 422 from `POST /registrations/walk-in` or `POST /invitations`.

- **Before:** `message` held pydantic's raw text, including the submitted
  values.
- **Now:** `message` reads `Invalid request: <field>: <reason>; …`. A new
  `errors` list gives each field separately, and submitted values are never
  echoed (see the appendix).
- **App:** map `errors[].field` to the matching input and fall back to
  `message`. Remove any parsing of the old raw text.

### A4. Upload limits (413) and new rate limits (429)
- **Uploads:** a multipart request above 160 MB in total or with more than
  100 files returns **413**. The per-file size limits still apply.
- **New per-client rate limits:**
  - signed file URLs (`/files/...`): 300/min;
  - `GET /form-builder/effective`: 120/min;
  - email images: 600/min.
- **App:** show "This upload is too large" for 413. For 429, show "Too many
  requests, try again in a moment" and back off; never retry 429 in a
  tight loop.

### A5. Hidden kiosks need a permission (if used)
`GET /kiosks?includeHidden=true`

- **Before:** hidden kiosks were returned to any caller.
- **Now:** `includeHidden` is ignored unless the caller's token holds
  `kiosks:view`.
- **App:** send the staff bearer token wherever the app lists hidden
  kiosks. If the app never uses `includeHidden`, answer "not used".

## B. Must ship before strict mode (target 2026-12-31)

Until `PUBLIC_ENDPOINT_HARDENING` is enabled, these calls behave as today,
plus a `Deprecation: true` header and a `Link` header pointing at the
feature docs. Strict mode is enabled only after the app team confirms a
released version covers every item here.

### B1. Device credential on tracking-ID check-in
`PATCH /api/v2/invitations/{trackingId}/check-in`

Strict mode requires one of:
- an approved `device-id` header;
- a staff bearer token holding `invitations:checkin` at that branch.

Otherwise it returns **401**, with no state change and no visitor data.
- **App:** kiosk and gate devices send their approved `device-id` on every
  check-in; staff screens send the staff token.

### B2. Tracking by email needs an OTP proof token
`GET /invitations/track?email=`

Strict mode requires `Authorization: Bearer <proofToken>` for the same
email, otherwise **401**. Tracking by tracking ID is unchanged.

```http
POST /api/v1/identity-verification/otp/request
{ "identifier": "ada@example.com", "channel": "email" }

POST /api/v1/identity-verification/otp/verify
{ "identifier": "ada@example.com", "channel": "email", "code": "123456" }
→ { "data": { "identifier": "ada@example.com", "channel": "email", "proofToken": "…" } }

GET /api/v1/invitations/track?email=ada@example.com
Authorization: Bearer <proofToken>
```

### B3. `X-Device-Key` on the kiosk lookups
`GET /hosts/search`, `GET /visit-info/departments`, `GET /visit-info/options`

- **Strict mode:** without `X-Device-Key`, each host search result's
  `email` is `null`.
- **App:** send the kiosk's `X-Device-Key` on all three, as walk-in
  registration already does.

### B4. Employee list needs a staff token (if used)
`GET /auth/employees`

- **Strict mode:** without a token holding `employees:view`, the list has
  only `id`, `fullName`, `designation`, `departmentId` and `avatarUrl`.
- **App:** staff screens send the staff token. A kiosk host picker should
  use `GET /auth/employees/directory`, which is built for that.

### B5. Kiosk reads need a staff token (if used)
`GET /kiosks`, `GET /kiosks/{id}`

- **Strict mode:** **401** without a token holding `kiosks:view`.
- **App:** call these only from signed-in staff screens. Device setup uses
  the device registration and `GET /devices/approval-status` endpoints.

### B6. Log `Deprecation: true` in test builds
- **App:** in debug and QA builds, log any response carrying
  `Deprecation: true` with its URL. A full test pass that logs none means
  the app is ready for strict mode.

## C. Recommended

| Item | Change | What the app does |
|---|---|---|
| C1 | `GET /auth/me`: `branchRoles[].permissionCodes` (new) | Show or hide actions by permission code (e.g. `invitations:checkin`) rather than by role name; tenants can define custom roles |
| C2 | `GET /invitations` items: `currentApprovalStep`, `preferredVisitDate`, `preferredVisitTime` (new) | Read these from the list instead of fetching each invitation's detail |
| C3 | `GET /invitations/{id}`: `checkInDevice`, `checkOutDevice` (new, nullable) | Show which device checked the visitor in and out |
| C4 | `visitDetails.purposeOfVisit` | Submit the display label ("Business Meeting"), which the web now stores and filters on. Show older slugs as labels: `business-meeting`, `interview`, `delivery`, `personal-visit`, `vendor-contractor`, `other`. The value can be `null` |
| C5 | Company `defaultTimezone` | Expect an IANA name (`Asia/Kolkata`); older companies may still return `GMT+05:30` |
| C6 | `GET /form-builder/effective` | Fetch it once per branch per session and reuse it (120/min limit) |
| C7 | `GET /invitations/track` `status` | Map `submitted` (under review), `approved`, `denied`, `checked_in`, `checked_out` and `archived` (expired, never came). Show any other value as is, neutrally |

## Appendix: response formats

Every JSON response uses the envelope `{ "success", "message", "data" }`;
error responses set `success: false`.

**422 validation error (new format):**

```json
{
  "success": false,
  "message": "Invalid request: visitors.0.email: value is not a valid email address",
  "errors": [
    { "field": "visitors.0.email", "message": "value is not a valid email address" }
  ]
}
```

| Status | When | App behaviour |
|---|---|---|
| 401 | Missing or expired staff token; in strict mode, a missing device or proof credential | Staff: back to sign-in. Device: re-check its approval status |
| 403 | Signed in, but the role lacks the permission | Keep the session and show "You don't have permission" |
| 409 | The same `Idempotency-Key` is still in progress | Wait, then retry with the same key |
| 413 | Upload above 160 MB or 100 files | Ask the user to remove or shrink files |
| 422 | Invalid input, or an `Idempotency-Key` reused for a different request | Show `errors[]` per field; for a reused key, start over with a new key |
| 429 | Rate limit reached | Show "try again in a moment" and back off |

**Deprecation headers** (legacy anonymous calls while strict mode is off):

```http
Deprecation: true
Link: <docs/features/invitations.md#public-endpoint-hardening>; rel="deprecation"
```
