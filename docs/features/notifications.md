# Notifications (Push)

Staff device registration and a push-notification dispatch primitive, built
on Firebase Cloud Messaging (FCM), for the React portal and the Flutter
app. Wired into the invitation/approval lifecycle so a host or approver
learns of an action awaiting or affecting them without refreshing the
portal — never the visitor, whose email/SMS notifications
(`docs/features/invitations.md`) are unchanged. See
`openspec/changes/add-invitation-push-notifications/` for the
proposal/design this feature was built from.

`notifications` is the general-purpose package `project-rules.md` and
`invitations/notifications.py`'s own docstring flagged as coming "once a
second feature needs it" — this is that feature. Other capabilities never
touch its `DeviceToken` table or the FCM SDK directly; they call
`notifications.service.notify_user`/`notify_role_at_branch`/
`notify_step_approver`.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/notifications/devices` | Any authenticated staff user (self-service, like `GET /auth/me` — no permission check) | Registers/updates a device token (`fcmToken`, `platform`: `web`/`android`/`ios`) against the caller's own account. Re-registering an already-known token updates it in place; a token previously owned by a *different* user is reassigned to the caller (a device is physically one browser/app install). |
| DELETE | `/api/v1/notifications/devices/{fcmToken}` | Any authenticated staff user | Removes one of the caller's own device tokens. A no-op (still 200), not an error, if the token was never registered or belongs to someone else. |
| GET | `/api/v1/notifications` | Any authenticated staff user (own notifications only) | The caller's in-app notifications, newest first. `page`/`pageSize` (default 20, max 100) and an optional `unreadOnly=true`. Each item: `id`, `title`, `body`, `data` (the push `data` verbatim), `createdAt`, `readAt`. |
| GET | `/api/v1/notifications/unread-count` | Any authenticated staff user | `{"unreadCount": n}` for the caller. |
| PATCH | `/api/v1/notifications/{id}/read` | Any authenticated staff user | Marks one of the caller's notifications read. Already read: 200, original `readAt` kept. Another user's or an unknown id: 404. |
| POST | `/api/v1/notifications/read-all` | Any authenticated staff user | Marks every unread notification of the caller read, in one statement. |

## Dispatch primitive

`notifications/service.py` exposes three functions other features call:

- `notify_user(*, tenant_schema, user_id, title, body, data)` — pushes to
  every device registered to one specific user.
- `notify_role_at_branch(tenant_db, *, tenant_schema, role_id, branch_id,
  title, body, data)` — resolves every user holding `role_id` via a
  `UserBranchRole` scoped to `branch_id`, or company-wide (`branch_id IS
  NULL`), then pushes to all of them. Zero holders logs `WARNING`
  (`push_notify_role_no_holders`) and is otherwise a no-op — not an error
  for the calling action.
- `notify_step_approver(tenant_db, *, tenant_schema, approver_user_id,
  approver_role_id, branch_id, title, body, data)` — the shared entry point
  `invitations`/`approvals` call with an `InvitationApprovalStep`'s own
  `approver_user_id`/`approver_role_id` XOR, routing to whichever of the two
  functions above applies.

A recipient resolved this way is never re-derived inside the Celery task —
`notifications/tasks.py::send_push` takes the already-resolved `user_ids`
and only resolves *devices* for them fresh at send time (which devices a
user has can change between enqueue and execution; who the recipient is
should not).

## Recipient resolution used by `invitations`/`approvals`

| Event | Recipient |
|---|---|
| Invitation submitted (workflow-backed, not auto-approved) | The newly-created first approval step's approver — host if host-identified, else every holder of the step's role at the invitation's branch, unless that role is the tenant's standard `admin` role. |
| A step is approved, activating the next step | The newly-current step's approver, same resolution as above. |
| Invitation approved / denied / rescheduled / checked in / checked out | The invitation's own host (`hostId`), if one resolved. No host means no push — not an error. |

A role-identified step pushes to every holder of that role, **except** the
tenant's standard `admin` role, which never receives push
(`exclude-admin-role-only-from-push`). `admin` is matched by name,
case-insensitively — it's seeded non-renameable/non-deletable per
`auth/rbac_catalog.py`, so it's a reliable identifier across every tenant. A
role id that can't be resolved to a row dispatches normally (fails open)
rather than silently dropping the push.

An auto-approved invitation never has approval steps, so its creation never
fires a "submitted, awaiting your approval" push — only the visitor's
existing auto-approval email fires. A `submitted` invitation with no
resolved host and no active workflow rules has no approval step at all;
that logs `WARNING` (`push_notify_no_approval_step`) rather than silently
doing nothing.

## Payload content

Every push payload is built by `invitations/push_notifications.py` from
`primary_contact_full_name`/`tracking_id`/`id` only — the one place
enforcing that a payload never carries identity-document data, raw OTP
codes, or other data `security-architecture.md` §2/§4 classifies as
sensitive, so it can't be bypassed per call site.

`notify_user`/`notify_role_at_branch` (`role-based-invitation-workflow`)
each add their own addressing metadata to the `data` dict on top of
whatever `push_notifications.py` built, so a client can tell *why* a given
push arrived without re-deriving it from `tracking_id`/`id` alone:

| Function | Extra `data` fields | Meaning |
|---|---|---|
| `notify_user` | `assignedUserId`, `reason: "delegated"` | This push targets one specific person because a step (usually the ownership step) was delegated to them — `assignedUserId` echoes that same user's id. |
| `notify_role_at_branch` | `assignedRoleId`, `reason: "role_assigned"` | This push fanned out to every holder of a role because a step is currently role-identified and un-delegated — `assignedRoleId` names that role. |

These fields are addressing metadata only, not new sensitive content — they
carry a `Role`/`User` id already implied by which step is current, nothing
`security-architecture.md` §2/§4 restricts.

## Failure handling

- Push dispatch always runs as a Celery task enqueued after the triggering
  action's own commit, never inline in the request path — a push failure
  (including full retry exhaustion) never surfaces on the triggering
  action's HTTP response.
- `send_push` declares `autoretry_for`/`retry_backoff`/`max_retries` like
  every task in `invitations/tasks.py`, and logs `ERROR`
  (`push_dispatch_exhausted`) with `tenant_schema`/`user_ids` on final
  exhaustion.
- A token FCM reports as "not registered" (app uninstalled, browser data
  cleared) is deleted from `device_tokens` so future dispatches stop
  attempting delivery to it — a transient send failure is left for the
  task's own retry instead.

## In-app feed and push state (`fix-web-push-and-add-notification-feed`)

- **Every dispatch is recorded.** `send_push` writes one `notifications`
  row per recipient (same title, body and `data` as the push), then commits,
  *before* looking up devices or calling FCM. A recipient with no device,
  or a send that exhausts its retries, still gets the in-app row.
  `(dispatch_id, user_id)` is unique: the service generates `dispatch_id`
  at enqueue time, so a redelivery or retry is an `ON CONFLICT DO NOTHING`.
  A recording failure logs `WARNING notification_record_failed` and the
  push still goes out.
- **Zero-device sends are logged.** `INFO push_no_registered_devices` with
  `recipient_count`. If staff report "no notifications", check this line
  and `device_tokens` first — a push to nobody used to look like success.
- **Retention.** Rows older than 90 days are hard-deleted by the
  visit-lifecycle sweep (every 15 minutes per tenant), in a commit separate
  from the sweep's own work. The sweep's log line reports
  `notifications_purged`.
- **Portal bell.** Loads the feed and unread count from the API on sign-in,
  on tab focus, every 60 seconds while visible, and when a foreground push
  arrives (the push itself only triggers a refetch). Clicking an item marks
  it read and opens its invitation; "Mark all read" calls `read-all`.
- **Push state.** The bell panel shows this browser's state: *enabled*,
  *off* (with **Enable notifications**), *blocked* (re-allow in the
  browser's site settings — a page can't re-prompt), or *unavailable*
  (insecure context or unsupported browser). Only that button asks for
  permission, because browsers suppress prompts not triggered by a click.
  Sign-in, tab focus and the 30-minute timer only re-register a browser
  that already granted permission.
- **Testing push locally.** Open the portal on `http://localhost:5173` or
  the DDEV HTTPS URL. On `http://<LAN-IP>:5173` the browser isn't a secure
  context, so push shows as unavailable (the in-app feed still works).
  Restart the DDEV Celery worker after changing `notifications/tasks.py`.

## Notification emails (`redesign-notification-email-templates`)

This section covers every templated email, not push: the invitation
emails dispatched by `invitations/tasks.py`, the verification-code email
(`identity_verification/service.py`) and the daily snapshot
(`reports/tasks.py`). They're rendered by
`core/email_rendering.py::render_email` from `core/email_templates/` and
sent through `core/emailing.py::build_message`.

**Layout** (`base.html`, restyled by
`refine-email-templates-and-visimio-brand`):
- a navy (`#0f172a`) header showing the tenant logo, else the Visimio
  logo image, else (no asset base URL configured) a styled "Visimio" text
  wordmark;
- a cyan accent rule;
- a white card with the tone-coloured status pill (when the type has one),
  the heading, the greeting (the OTP email has none), and the per-type
  sections;
- a footer reading "Sent by {company or Visimio}", the no-reply line,
  "Powered by Visimio", and "© {year} Visimio. All rights reserved.".

The Visimio logo is `core/email_assets/visimio-logo-on-dark.png`, generated
by `scripts/build_brand_assets.py`, and served publicly (see "Images load
by URL" below). The From header carries the display name `SMTP_FROM_NAME` (default
"Visimio").

The layout is table-based with inline styles, 600px wide, and fluid below
that. One `<style>` block carries only the ≤620px media query and the
font import, both of which degrade safely.

**Tones** (`email_rendering.TONES`, chosen per template by
`TEMPLATE_TONES`) colour the pill, callouts, highlight boxes and QR
panel:

| Tone | Used by |
|---|---|
| success (green) | confirmation |
| pending (amber) | received, triage |
| danger (red) | not approved |
| info (blue) | rescheduled, details updated |
| brand (teal) | host / POC assigned, verification code, snapshot |

Every tone's text colours pass WCAG AA, which is unit-tested.

**Building blocks** (`_macros.html`, imported `with context`):
`highlight_box` (a dashed box for the tracking ID or code), `timeline`,
`checklist`, `section`, `visit_details`, `detail_table`, `callout`,
`qr_pass`, `note`, and `tracking_note`. `visit_details` always renders the
same rows: date & time, **place of visit** (building · branch · address,
city, from `InvitationRepository.get_location`), department (catalog name,
else free text), duration, and purpose.

**Per-type content** (`<type>.html` + `<type>.txt`; subject = heading):

| Template | To | Pill / heading | QR |
|---|---|---|---|
| `visit_confirmation` | Visitor | Confirmed / Your visit is confirmed | Signed URL |
| `tracking_only` | Visitor | Pending approval / We've received your visit request | — |
| `denial` | Visitor | Not approved / Your visit request wasn't approved | — |
| `reschedule` | Visitor | Rescheduled / Your visit has been rescheduled | Signed URL if approved |
| `edit` | Visitor | Details updated / Your visit details have changed | — ("still valid" if approved) |
| `submission_role` | Role holders | Action needed / New visit request awaiting triage | — |
| `host_assigned` | Host | You're the host / You've been named host for a visit | — |
| `poc_assigned` | POC user | Point of contact / You're the point of contact for a visit | — |
| `verification_code` | OTP requester | — / Your verification code | — |
| `daily_snapshot` | Tenant admins | Daily snapshot / Daily branch rollup — {date} | — |

**Point of contact** (`serve-email-images-by-url-and-complete-contact`):
confirmation, reschedule and edit always show a "Your point of contact"
block. `invitations/tasks.py::_resolve_contact` takes the first available
of:
1. the invitation POC (name, plus phone or email when it's a user);
2. the resolved host;
3. the branch's contact person (`Branch.contact_person_user_id`);
4. "Front desk" with the branch's `contact_phone`/`contact_email`, else the
   Company phone/email;
5. "Reception at {branch name}" (or "Reception") with no detail.

A candidate whose name fails `display_name` is skipped, not shown.

**Rules every template follows:**
- `detail_table` / `detail_rows` drop a row whose value is missing, so no
  row ever shows blank or "None".
- The `display_name` filter returns no name when the stored one is blank,
  equals the email, or is a 16+ character whitespace-free id-like token.
  That's what an IdP sends when it has no `name` claim. The greeting then
  reads "Hello," and third-party names fall back to "your visitor".
- The `visit_datetime` filter renders `Wed, 14 Oct 2026 · 10:30 AM` using
  fixed English day and month names, so the output doesn't depend on the
  container locale.
- The hidden preheader (the inbox preview line) is the heading plus the
  tracking ID. The Mailpit tests match messages on that snippet.

**Images load by URL** (`serve-email-images-by-url-and-complete-contact`):
with `EMAIL_ASSET_BASE_URL` set, every image is an absolute `<img src>`
and the delivered message is just `multipart/alternative` (text + HTML) —
no attachment and no inline part, so no client shows an attachment strip.
- Logo: `GET /api/v1/public/email-assets/visimio-logo.png`
  (`core/email_assets_router.py`, `Cache-Control: public, max-age=31536000,
  immutable`; rename the file to bust caches).
- Check-in QR: `GET /api/v1/public/email-assets/{tenantId}/qr/{invitationId}.png?exp=&sig=`
  (`invitations/email_assets_router.py`). `sig` is an HMAC-SHA256 over
  `qr:{tenant}:{invitation}:{exp}` (`core/email_assets.py`); `exp` is the
  invitation's `expires_at` + 7 days, computed at send time. 403 bad
  signature (logged at WARNING), 410 expired, 404 unknown tenant /
  invitation / QR. Rate-limited 60/minute per IP; `Cache-Control: private,
  max-age=86400`. The PNG is regenerated from the token persisted at
  approval, so it's identical to what the check-in scanner expects.

The QR sits on a white, padded cell so dark-mode clients keep it
scannable, and the tracking ID is always printed under it — a client that
blocks remote images (Outlook desktop until "show images") can still check
in by tracking ID.

**Fallback** when `EMAIL_ASSET_BASE_URL` is unset: `render_email` logs
`email_asset_base_url_unset` at WARNING once per process, the header shows
the text wordmark, and the QR is embedded as a single `cid:visit-qr@vmss`
inline part (`EmailSender.send(..., inline_images=[...])`). Never an
attachment either way.

**Portal links** (`add-portal-links-to-emails`): with `STAFF_PORTAL_URL`
set, eight emails carry one call-to-action button, plus the same URL as a
`{label}: {url}` line in the plain-text part. URLs are built only in
`core/portal_links.py`, and each email's label/URL pair lives in
`invitations/tasks.py::_CTAS`:

| Email | Recipient | Button | Link |
|---|---|---|---|
| `tracking_only` | Visitor | Track your request | `/visitor/track` |
| `visit_confirmation` | Visitor | View your visit | `/visitor/track` |
| `reschedule` | Visitor | View your visit | `/visitor/track` |
| `edit` | Visitor | View your visit | `/visitor/track` |
| `denial` | Visitor | Submit a new request | `/visitor/request` |
| `submission_role` | First-step role holders | Review request | `/staff/login` |
| `host_assigned` | Host | View visit | `/staff/login` |
| `poc_assigned` | Point of contact | View visit | `/staff/login` |

- The verification-code and daily-snapshot emails carry no link. The
  code email is deliberately link-free, because a code plus a link is the
  phishing pattern.
- Links are fixed page paths, with no tracking ID, invitation id or any
  other personal data. The tracking-ID sentence stays, because the reader
  enters that ID on the track page, or searches for it after signing in.
- The plain-text render-failure fallback carries the same link.
- `STAFF_PORTAL_URL` is the web app's origin, supplied per environment
  through the existing `__STAFF_PORTAL_URL__` pipeline token in `.env`
  (and `k8s.yml`). Despite its name, visitor links use it too. Only its scheme + host is
  used, so a value like `https://host/staff/login` is fine. If it's
  unset, or isn't an `http(s)://` URL (e.g. an unreplaced token), emails
  go out without the button, and `portal_base_url_unset` is logged at
  WARNING once per process.
- No VMMS_WEB change is needed: all three linked pages already exist.

**Previewing:** `ddev exec uv run python scripts/send_email_previews.py`
sends all ten templates, with full sample data and `[Preview]` subjects,
to `preview@visimio.local` in Mailpit (`ddev mailpit`). The QR previews
use a real signed URL for the tenant's latest invitation with an issued
QR, or the inline fallback otherwise. `--to` and `--tenant-slug` override
the defaults. Mailpit's HTML Check tab shows the per-client support
breakdown.

## Config knobs

| Setting | Default | Purpose |
|---|---|---|
| `EMAIL_ASSET_BASE_URL` | unset (DDEV: `https://vmss-new-api.ddev.site:8443`) | Public origin of this API that email images load from. **Required in production**; unset falls back to a text wordmark and an inline QR. |
| `EMAIL_ASSET_URL_SECRET` | unset | Signs QR image URLs; falls back to `STORAGE_LOCAL_URL_SECRET`, then `JWT_SECRET_KEY`. Rotating it invalidates QR images in already-sent emails (the tracking ID still works). |
| `STAFF_PORTAL_URL` | unset (pipeline token `__STAFF_PORTAL_URL__`) | Public origin of the web app (VMMS_WEB) that every email button links to, visitor and staff alike. See "Portal links" above. Unset, or not an `http(s)://` URL, means emails are sent without links. |
| `FCM_CREDENTIALS_PATH` | unset | Path to a Firebase service-account key JSON file. Left unset by default; `notifications/fcm.py` fails loudly (`FcmNotConfiguredError`) the first time a push is actually attempted, rather than silently no-op'ing — same posture `TWILIO_*`/`SMS_GATEWAY_*` already have. |

## Not yet built (flagged, not silently dropped)

- **Client-side registration UI.** The React portal's and Flutter app's own
  push-permission prompts and service-worker/FCM-token wiring are separate
  repos; this feature only builds the API side (registration endpoint +
  dispatch). The endpoint is usable the moment either client implements
  its side.
- **Notification preferences/opt-out.** Every user with a registered
  device receives every push their role/host relationship entitles them
  to; there's no per-user mute/preference setting.
- **Push beyond `invitations`/`approvals`.** Blacklist changes, admin
  config changes, and login are not wired to push yet — deliberately
  scoped out of this change (see the proposal), left for a later change to
  pick up using the same `notify_user`/`notify_role_at_branch` primitives.
