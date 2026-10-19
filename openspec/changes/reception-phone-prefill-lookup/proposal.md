## Why

On the staff (Reception) "Register Visitor" form, Primary Contact Details are typed by hand even when the visitor has registered before. The email lookup (`GET /invitations/lookup-by-email`) already prefills the form, but reception usually has the visitor's phone number first, and email is the required field they must otherwise ask for and type. Entering a phone number should prefill Full Name, Email and the other known details when that visitor is already in the database. The OTP-gated visitor portal prefill already works and is out of scope.

## What Changes

- Add `GET /invitations/lookup-by-phone?phone=<phone>`, a staff-authenticated, branch-scoped lookup that returns the prefill payload from the most recent matching invitation, or `data: null` when none exists.
- Match phone numbers on normalized digits, so `+91 95442 32271`, `95442-32271` and `9544232271` resolve to the same visitor.
- Include `email` in the prefill payload. It is the key on the email lookup, so it was never returned there. This is an additive, non-breaking field.
- Apply the same permission rules as the email lookup: `invitations:create` required, `photoUrl` always resolved, `idProofUrl` only with `documents:view`.
- Add a functional index so the normalized-phone match does not scan `invitations`.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `invitations`: adds a staff phone-based prefill lookup requirement, and adds `email` to the existing prefill payload shape.

## Impact

- Code: `invitations/router.py`, `service.py`, `repository.py`, `schemas.py` (`InvitationLookupPrefillOut`), plus a new `alembic_tenant` migration for the index.
- API: one new endpoint and one new optional response field on `lookup-by-email`. No breaking change, so it stays in `/api/v1`.
- Docs: `docs/features/invitations.md`, and Swagger via `response_model`.
- Frontend (separate repo): Reception form calls the endpoint when the phone field is complete (on blur or debounce) and fills empty fields.
- No new permission codes and no new dependencies.
