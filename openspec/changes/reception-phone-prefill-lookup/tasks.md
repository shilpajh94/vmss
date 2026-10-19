## 1. Schema and migration

- [x] 1.1 Add optional `email` to `InvitationLookupPrefillOut` in `invitations/schemas.py`
- [x] 1.2 Add an `alembic_tenant` migration creating the functional index on `regexp_replace(primary_contact_phone, '\D', '', 'g')`, with downgrade
- [x] 1.3 Add a shared digits-only phone normalizer and use it for query input validation (minimum 7 digits)

## 2. Repository and service

- [x] 2.1 Add `InvitationRepository.get_latest_for_prefill_by_phone(phone_digits, branch_scope)` with the same soft-delete and branch filters as the email variant
- [x] 2.2 Extract the prefill-building code from `get_prefill_by_email` into a shared helper that also sets `email`
- [x] 2.3 Add `service.get_prefill_by_phone` using the helper, logging the masked phone at `INFO`

## 3. Router and docs

- [x] 3.1 Add `GET /invitations/lookup-by-phone` with `response_model=Envelope[InvitationLookupPrefillOut | None]`, `-> JSONResponse`, `require_branch_scope("invitations:create")`
- [x] 3.2 Update `docs/features/invitations.md` with the endpoint and the `email` field

## 4. Tests

- [x] 4.1 Happy path: match returns newest invitation's name and email
- [x] 4.2 Formatting-insensitive match (`+91 95442-32271` vs `919544232271`)
- [x] 4.3 No match returns `data: null`; too-short phone returns a validation error
- [x] 4.4 Permission-denied: caller with only `invitations:view` gets `403`
- [x] 4.5 Branch isolation: other-branch match and `X-Branch-ID` narrowing return `data: null`
- [x] 4.6 `idProofUrl` null without `documents:view`, resolved with it; `photoUrl` resolved either way
- [ ] 4.7 Tenant-isolation test against a second tenant schema
- [ ] 4.8 Regression: `lookup-by-email` still passes and now includes `email`
- [ ] 4.9 Run `ruff check`, `ruff format --check`, and `pytest`
