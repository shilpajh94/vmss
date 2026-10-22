## Why

Reception can already prefill the Register Visitor form by typing a returning visitor's email, but many walk-ins give only a phone number. The backend now exposes `GET /invitations/lookup-by-phone`, so reception can prefill from a phone number too and avoid retyping known details.

## What Changes

- Add a staff-authenticated phone lookup (`GET /invitations/lookup-by-phone?phone=<phone>`) behind the existing clean-architecture layers: endpoint registry entry, port method, adapter, use case, composition-root wiring.
- Prefill the Primary Contact on the Register Visitor wizard once the phone field holds at least 7 digits (debounced), mirroring the existing email lookup.
- Prefill **only fields that are still empty** (full name, email, preferred contact method, visitor category, ID proof type, photo; ID proof file when returned) so nothing reception typed is overwritten. This also applies to the email lookup's prefill rules where the two share logic, so both lookups behave consistently.
- `data: null`, a 422 or any failure leaves the form untouched and shows no error.
- Extend the lookup schema with a nullable `email` (backend now returns it from both lookups; additive).
- `idProofUrl` may be `null` (requires `documents:view`); handled as "no ID proof file to prefill".

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `staff-visitor-registration`: adds requirements for phone-based prefill of the primary contact and the "fill only empty fields" rule.

## Impact

- Code: `src/data/api/api-endpoints.ts`, `src/data/repositories/staff-visitor-lookup-repository.ts`, `src/infrastructure/staff-visitor-lookup-repository.ts`, `src/domain/entities/staff-visitor-lookup-schema.ts`, new `src/data/use-cases/lookup-staff-visitor-by-phone.ts`, `src/composition-root.ts`, and `use-staff-visitor-registration-wizard.ts`.
- API: new consumer of `lookup-by-phone`; backend endpoint is not yet deployed, so end-to-end verification depends on deployment.
- Risk: `X-Branch-ID` handling and prod CORS (see design).
