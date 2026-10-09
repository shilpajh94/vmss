## Context

The current email setup is described in proposal.md, which also lists every email in its audit table. The facts that shape this design:

- All templated emails go through `core/email_rendering.py::render_email`.
  It already adds shared keys to the context (`logo_src`, `current_year`,
  `staff_portal_url`), and `_macros.html` already has a `button(label, url)`
  macro. Only `submission_role` uses it today.
- Invitation emails build their context in
  `invitations/tasks.py::_invitation_email_context`. The context carries
  `tracking_id` but not the invitation `id`.
- The render-failure fallback body is hard-coded in
  `invitations/tasks.py::_render_or_fallback`.
- VMMS_WEB is one SPA at one origin, with visitor routes (`/visitor/track`,
  `/visitor/request`) and the staff sign-in (`/staff/login`) side by side.

## Goals / Non-Goals

**Goals:**
- One place builds every portal URL, so the path contract with VMMS_WEB
  lives in a single module.
- Templates choose where the button sits. Tasks choose the URL. Neither
  knows how the other works.

**Non-Goals:**
- Per-tenant portal domains (custom domains / subdomains). One origin for
  every tenant, the same as the current SPA deployment.
- Signed or expiring "magic" links that log a user in or reveal visit
  details without authentication. The visitor link only pre-fills the
  public tracking lookup, and the staff link still requires login.
- Links in SMS / WhatsApp bodies, and new emails for the push-only events
  (later approval steps, delegation). Both are flagged as follow-ups in
  proposal.md.
- Deep links to a specific invitation or a pre-filled tracking lookup (see
  Decision 4).

## Decisions

### 1. Reuse the existing `STAFF_PORTAL_URL` pipeline token
Environments get their values from `__KEY__` tokens in the committed
`.env`, which `replacetokens` fills in per environment (`CI-CD/*.yml`, plus
`k8s.yml`'s `KEY: "$(KEY)"`). `STAFF_PORTAL_URL=__STAFF_PORTAL_URL__` is
already wired through all of that, and visitor and staff pages share one
SPA origin. So that one setting is the base for every link, and no
`.env`, pipeline variable or manifest change is needed. A value that is
blank or isn't `http(s)://` (such as an unreplaced token) counts as unset,
so a misconfigured environment sends no link instead of a broken one.
*Alternative considered:* a new `PORTAL_BASE_URL`. Rejected because it
would need a new token in `.env`, a new pipeline variable in every
environment, and a new manifest entry, all to carry the same value
`STAFF_PORTAL_URL` already carries. The name is narrower than its use
now; a comment in `core/config.py` says so.

### 2. A `core/portal_links.py` module owns the URL paths
Functions: `visitor_track_url()`, `visitor_request_url()` and
`staff_login_url()`. Each returns `str | None`, where `None` means the base
URL is unset. This module also issues the once-per-process `WARNING`
(`portal_base_url_unset`), following `_logo_src`'s existing pattern.
*Alternative considered:* building the URLs inside the Jinja templates from
a base-URL variable. Rejected because the fallback path
(`_render_or_fallback`) needs the same URLs without a template, and the
paths should be unit-testable in one place.

### 3. One label/URL table in `invitations/tasks.py`, rendered via `cta`
`_invitation_email_context` adds `visitor_track_url`, `visitor_request_url`
and `staff_login_url` to the shared context. A module-level `_CTAS`
table maps each template to its button label and the context key that
holds its URL. `_render_or_fallback` resolves that into
`cta = {"label", "url"}` (or `None` when the portal URL is unset) before
rendering, and the fallback body reuses the same pair. Each affected
`.html` calls `{% if cta %}{{ m.button(cta.label, cta.url) }}{% endif %}`
and the matching `.txt` emits `{{ cta.label }}: {{ cta.url }}`.
*Alternative considered:* each task setting its own `cta`. Rejected
because it spreads the 8 labels across 8 task bodies, and the fallback
would then need them passed separately. `render_email` stops injecting
`staff_portal_url`, and `submission_role` switches to `cta`, which drops
the root-link button.

### 4. Links open existing pages only: fixed paths, no deep links
Visitor emails link to `/visitor/track` (denials to `/visitor/request`),
and staff emails link to `/staff/login`. All three routes already exist in
VMMS_WEB, so this change ships with no web dependency. The reader then
enters the tracking ID printed in the email (visitor), or signs in and
finds the request on their board (staff). *Alternatives considered:* a
pre-filled `/visitor/track?trackingId=` link, and a role-neutral
`/invitations/{id}` staff route that survives login. Both were dropped
at the product owner's request, because each needs new VMMS_WEB work
first. Either can be added later without changing the email layout; only
the path in `portal_links` changes.

### 5. The verification-code email gets no `cta`
`identity_verification/service.py` never passes one. A test asserts that
the rendered output contains no `href` and no URL (spec "Verification-Code
Email Carries No Links").

## Risks / Trade-offs

- [Readers still have to type or search the tracking ID] → Accepted for
  now (Decision 4). The tracking-ID note stays next to every button.
- [Admins and reception users sign in at `/admin/login`, not
  `/staff/login`] → Staff emails go to staff-role holders, hosts and POCs,
  who use `/staff/login`. An admin who gets one can still switch to the
  admin login from there.
- [Corporate mail scanners pre-fetch links] → Every link is a GET to an SPA
  page with no side effects, so a pre-fetch changes nothing.

## Migration Plan

1. Deploy this change. Check that each environment's `STAFF_PORTAL_URL`
   pipeline variable is the SPA's origin (scheme + host).
2. Rollback: blank the `STAFF_PORTAL_URL` pipeline variable. Emails go
   back to having no links. No data or schema is involved.
