## 0. Cross-repo prerequisite

- [x] 0.1 None needed: links target existing VMMS_WEB pages (`/visitor/track`, `/visitor/request`, `/staff/login`) per design.md Decision 4

## 1. Configuration

- [x] 1.1 Use the existing `staff_portal_url` (`STAFF_PORTAL_URL`, pipeline token `__STAFF_PORTAL_URL__`) as the link base, and update its comment in `core/config.py`
- [x] 1.2 No `.env`/`.env.example`/pipeline change: the token is already wired through every environment

## 2. Link builder

- [x] 2.1 Create `core/portal_links.py` with `visitor_track_url`, `visitor_request_url`, and `staff_login_url`. They resolve `STAFF_PORTAL_URL` (treating blank or non-`http(s)://` values, such as an unreplaced token, as unset), strip whitespace and trailing `/`, and return `None` when the base URL is unset
- [x] 2.2 Log `portal_base_url_unset` at `WARNING` once per process when the base URL is unset (following the `_logo_src` pattern)
- [x] 2.3 Unit tests: correct paths, trailing-slash normalisation, unreplaced-token handling, `None` plus a single warning when unset

## 3. Templates

- [x] 3.1 Add `{% if cta %}{{ m.button(cta.label, cta.url) }}{% endif %}`, placed after the detail sections and before the tracking note, to `tracking_only`, `visit_confirmation`, `reschedule`, `edit`, `denial`, `host_assigned` and `poc_assigned` `.html`
- [x] 3.2 Add the matching `{{ cta.label }}: {{ cta.url }}` line to each corresponding `.txt`
- [x] 3.3 Switch `submission_role.html`/`.txt` from `staff_portal_url` to `cta`, and remove `staff_portal_url` injection from `render_email`

## 4. Wiring the links into dispatch

- [x] 4.1 `_invitation_email_context` adds `visitor_track_url`, `visitor_request_url` and `staff_login_url`
- [x] 4.2 Each visitor task (approval, tracking, reschedule, edit) sets `cta` to "Track your request" or "View your visit" with the track URL. The denial task sets "Submit a new request" with `visitor_request_url()`
- [x] 4.3 The submission-role, host-assigned and POC-assigned tasks set `cta` to "Review request" or "View visit" with `staff_login_url`
- [x] 4.4 `_render_or_fallback` appends `"{label}: {url}"` to the fallback body when the context has a `cta`
- [x] 4.5 Confirm `identity_verification/service.py` passes no `cta` to `verification_code`

## 5. Tests (`tests/test_email_notifications.py`)

- [x] 5.1 For each of the eight types: with the base URL set, the HTML contains the button with the exact URL and label from the spec table, and the plain text contains the `label: url` line
- [x] 5.2 Submission-role email contains no link to the bare base URL
- [x] 5.3 With the base URL unset: no button and no link line, the email still sends, and the warning is logged once across several renders
- [x] 5.4 Verification-code email: no `<a href` and no `http(s)://` in either part, even with the base URL set
- [x] 5.5 No link in any email contains the visitor's name, email, phone or ID-proof number
- [x] 5.6 Fallback email includes the CTA URL when rendering fails
- [x] 5.7 Run `ruff check`, `ruff format --check`, `mypy` (core), and `ddev exec uv run pytest tests/test_email_notifications.py src/vmss_api/invitations`, then the full suite

## 6. Docs

- [x] 6.1 Update `docs/features/notifications.md` and `docs/features/invitations.md` with the per-email link table and the `STAFF_PORTAL_URL` setting, including the web-route dependency and the deploy order from design.md's Migration Plan
