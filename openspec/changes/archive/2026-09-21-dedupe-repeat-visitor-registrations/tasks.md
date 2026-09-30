## 1. Repository

- [x] 1.1 Add `InvitationRepository.get_latest_by_primary_contact_email(email: str) -> Invitation | None` to `src/vmss_api/invitations/repository.py`, querying `Invitation.primary_contact_email == email` (`deleted_at IS NULL`), ordered by `created_at DESC`, `LIMIT 1` — no eager-load of children needed (only `primary_contact_full_name`/`primary_contact_email` are read).
- [x] 1.2 Add `InvitationRepository.get_latest_by_primary_contact_phone(phone: str) -> Invitation | None`, same shape as 1.1 but filtering on `Invitation.primary_contact_phone == phone`.

## 2. Service

- [x] 2.1 In `create_invitation` (`src/vmss_api/invitations/service.py`): when `payload.primary_contact.email` is non-null, call `get_latest_by_primary_contact_email`. When it is null and `payload.primary_contact.phone` is non-null, call `get_latest_by_primary_contact_phone` instead. Never call both on the same request.
- [x] 2.2 Resolve `full_name`/`email` locals: if a match was found (either lookup), use the matched invitation's `primary_contact_full_name` and `primary_contact_email`; otherwise use `payload.primary_contact.full_name` and `payload.primary_contact.email` as submitted. Use these locals everywhere the new `Invitation`'s corresponding columns are set.
- [x] 2.3 Confirm a submitted, non-matching email always results in "no match" (first-time treatment) and never falls through to a phone-based match against a different prior invitation.
- [x] 2.4 Confirm no other primary-contact field, visit-detail field, or `InvitationVisitor` construction path is touched by this lookup.

## 3. Tests

- [x] 3.1 `invitations/tests.py`: first-time email creates an invitation with the submitted `primaryContactFullName` unchanged (existing behavior, regression guard).
- [x] 3.2 `invitations/tests.py`: a second invitation created with an email matching a prior invitation, submitting a different `primaryContactFullName`, results in the new invitation storing the *prior* invitation's `primaryContactFullName`, and the response reflects the stored (not submitted) value.
- [x] 3.3 `invitations/tests.py`: the same returning-email scenario with a different submitted phone number, visitor category, and visit details confirms those fields are stored exactly as newly submitted (not carried over).
- [x] 3.4 `invitations/tests.py`: a prior invitation in `denied` status (or with `expires_at` in the past) still causes the name lock to apply on a new submission with the same email.
- [x] 3.5 `invitations/tests.py`: a primary contact submitted with phone only (no email), where that phone matches a prior invitation, results in the new invitation's `primaryContactFullName` and `primaryContactEmail` both being carried forward from that prior invitation.
- [x] 3.6 `invitations/tests.py`: a primary contact submitted with phone only (no email), where that phone matches nothing, is treated as first-time (submitted `primaryContactFullName` used as-is, `primaryContactEmail` stays null).
- [x] 3.7 `invitations/tests.py`: a primary contact submitted with an email that matches no prior invitation, but whose phone matches a *different* prior invitation's phone, is treated as first-time — `primaryContactFullName` and `primaryContactEmail` are exactly what was submitted, not locked to the phone-matched invitation.
- [x] 3.8 `invitations/tests.py`: a returning-contact submission still results in two distinct rows in `invitations` (query both by tracking ID) — the prior row's own `primary_contact_full_name`/`primary_contact_email` is unchanged.
- [x] 3.9 `registrations/tests.py` (or equivalent walk-in coverage): the same returning-contact lock behavior (both email match and phone fallback) holds via `POST /registrations/walk-in`.
- [x] 3.10 `invitations/tests.py`: a `group` invitation where a co-visitor shares an email with a person listed as a co-visitor on an earlier invitation stores that co-visitor's `fullName` exactly as submitted — confirms co-visitors are unaffected.

## 4. Documentation

- [x] 4.1 Update `docs/features/invitations.md` (or the equivalent existing doc) to describe the returning-primary-contact name lock, per `api-documentation.md`/`project-rules.md`'s expectation that a changed endpoint's behavior is reflected in its feature doc.
