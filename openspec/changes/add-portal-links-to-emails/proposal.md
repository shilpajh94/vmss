## Why

Our notification emails tell people to "open the visitor management portal
and search for tracking ID …" but never give them the address. A visitor
holding a tracking ID has to find the site on their own before they can use
it, and a host or approver has to open the portal and search for the request
by hand. Only one email today, the "awaiting triage" email, has a button.
It goes to the portal's front page, not to the request, and it only appears
when the undocumented `STAFF_PORTAL_URL` is set. A link that opens the right
page on the website removes that friction from every email that asks the
reader to do something.

## Email-by-email audit

These are all the emails the system sends today, found by tracing every
`email_sender.send` call site:

| # | Email (template) | Recipient | Trigger | Gets a link? | Link opens |
|---|---|---|---|---|---|
| 1 | We've received your visit request (`tracking_only`) | Visitor | Invitation created, pending approval | **Yes**: "Track your request" | Visitor track page (`/visitor/track`) |
| 2 | Your visit is confirmed (`visit_confirmation`) | Visitor | Approved (or auto-approved on create) | **Yes**: "View your visit" | Visitor track page (`/visitor/track`) |
| 3 | Your visit has been rescheduled (`reschedule`) | Visitor | Reschedule | **Yes**: "View your visit" | Visitor track page (`/visitor/track`) |
| 4 | Your visit details have changed (`edit`) | Visitor | Edit | **Yes**: "View your visit" | Visitor track page (`/visitor/track`) |
| 5 | Your visit request wasn't approved (`denial`) | Visitor | Deny | **Yes**: "Submit a new request" | Visitor request form |
| 6 | New visit request awaiting triage (`submission_role`) | Staff holding the first-step role at the branch | Invitation submitted | **Yes**: "Review request". This replaces today's generic "Open staff portal" button. | Staff sign-in (`/staff/login`) |
| 7 | You've been named host for a visit (`host_assigned`) | Host | Host assigned during approval | **Yes**: "View visit" | Staff sign-in (`/staff/login`) |
| 8 | You're the point of contact for a visit (`poc_assigned`) | POC | POC set on edit | **Yes**: "View visit" | Staff sign-in (`/staff/login`) |
| 9 | Daily branch rollup (`daily_snapshot`) | Tenant admins | Scheduled daily | **Not in this change** (descoped during apply; candidate follow-up) | — |
| 10 | Your verification code (`verification_code`) | Visitor (OTP) | OTP request | **No** | n/a. The reader is already on the site, and a one-time-code email that also contains a link is the usual pattern of a phishing email. Security guidance is to keep code emails link-free. |
| 11 | Minimal plain-text fallback (any of 1–8 when rendering fails) | Same as the failed email | Template render failure | **Yes** (for 1–8): the same link the failed template would have carried | Same as the failed email |

Gaps found during the audit. These are not emails today, so they are out of
scope, but they are worth deciding on next: later approval steps
(`step_awaiting_approval`) and delegation notify staff **only by push**,
with no email. SMS bodies also carry no link.

## What Changes

- Every email link is built from the existing `STAFF_PORTAL_URL` setting,
  the web app's origin. Each environment already supplies it through the
  `__STAFF_PORTAL_URL__` pipeline token, so no `.env` or pipeline change
  is needed. A blank value, or one that isn't `http(s)://` (such as an
  unreplaced token), counts as unset.
- Add a call-to-action button, plus the same URL written out in the
  plain-text part, to emails 1–8 as listed in the table above. Each email
  links to the page where the reader can act on that specific
  request, not just the site's home page.
- The minimal plain-text fallback email includes the same link.
- When the portal URL is unset, emails render exactly as they do today
  with no button, and a `WARNING` is logged once per process. Sending is
  never blocked by a missing link.
- The verification-code email stays link-free. This becomes an explicit
  requirement.
- Links open existing web pages only, so no VMMS_WEB change is needed.
  Visitors enter their tracking ID on the track page, and staff sign in
  and find the request on their board.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `email-notifications`: new requirements say which emails carry a portal
  link and where each one points, how links behave when the portal URL is
  not configured, and that the verification-code email stays link-free. The
  fallback-email requirement is changed to include the link.
- `environment-configuration`: none. The existing "Every Setting Is
  Documented in the Example File" requirement already covers the new
  setting, so this capability needs no delta.

## Impact

- **Code:** `core/config.py` (setting comment), a new
  `core/portal_links.py` URL builder, `core/email_rendering.py` (passes the
  links into the template context), `core/email_templates/*.html|*.txt`
  (emails 1–8), `invitations/tasks.py` (per-email link context and the
  fallback body).
- **Config:** none. `STAFF_PORTAL_URL` is already a pipeline token in
  `.env` and `k8s.yml`.
- **No API contract change:** no endpoints, request schemas or response
  schemas change.
- **Cross-repo:** none. All linked pages already exist in VMMS_WEB.
