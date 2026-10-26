## Context

Employees are created through `HttpHostEmployeeRepository.create`, which re-sends the full roster to `SYNC_EMPLOYEES` plus the new entry (no per-employee create endpoint exists). Staff sign in via `/auth/login` with email + password. The form lives in `admin-host-employee-form.tsx` with state in `use-admin-host-employee-form.ts`.

## Goals / Non-Goals

**Goals:**
- Let an admin optionally set an initial password when adding an employee.

**Non-Goals:**
- Changing/resetting a password on the Edit page.
- Auto-generated passwords, invitation/reset emails, or forced change on first login.
- SSO login (separate roadmap).

## Decisions

- **Optional, manual entry.** The field is optional so existing flows (and employees who will use SSO later) are unaffected. Alternative (required) rejected: would break current usage.
- **Transport via `POST /auth/users`.** The backend's sync item schema has no password (verified in `/openapi.json`; an earlier plan to send it there was silently ignored). `create` calls `CREATE_STAFF_USER` with email, password, fullName **before** the sync, because the sync registers the email and `/auth/users` then fails with "Email already registered" (observed on stage). Failure surfaces as the existing create-error toast.
- **Validation:** min 8 characters, client-side only; backend remains authoritative. Error text shown under the field, matching existing field-error pattern.
- **UI:** reuse the existing form input component; add a show/hide toggle using icons from `assets/icons` barrel. Field spans the full row below Role/Branch.
- **Handling:** password stays in hook state, is trimmed of nothing (whitespace is significant), and is omitted from the payload when empty.

## Risks / Trade-offs

- [`/auth/users` may conflict with the sync-created employee (duplicate email) or not link to it] → unverified: the sync is expected to link the pre-created user by email. If not, ask backend for a password on employee create. A sync failure after the user call leaves a user without an employee, and a retry hits "Email already registered".
- [Plaintext password in the request body] → same as login; relies on HTTPS. Do not log it or put it in toasts.
- [Browser autofill filling the field] → set `autoComplete="new-password"`.
