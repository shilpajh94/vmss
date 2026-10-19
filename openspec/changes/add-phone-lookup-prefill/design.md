## Context

The Register Visitor wizard (`use-staff-visitor-registration-wizard.ts`) already has a debounced email lookup (`LookupStaffVisitorByEmailUseCase` → `HttpStaffVisitorLookupRepository.lookupByEmail` → `LOOKUP_STAFF_VISITOR_BY_EMAIL`). It overwrites name/phone/etc. unconditionally and does not send `X-Branch-ID`. The phone lookup returns the same shape plus `email`. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Reuse the existing lookup repository/schema; add phone as a sibling operation.
- One shared "apply match to empty fields" routine used by both lookups.

**Non-Goals:**
- Looking up additional group visitors.
- Changing the public (visitor) wizard or the visitor-portal prefill.
- Backend changes.

## Decisions

1. **Extend, don't fork, the lookup port.** Add `lookupByPhone(phone)` to `StaffVisitorLookupRepository`, a new `LOOKUP_STAFF_VISITOR_BY_PHONE` endpoint (`/invitations/lookup-by-phone`, GET, `hasToken: true`), a `LookupStaffVisitorByPhoneUseCase`, and a `lookupStaffVisitorByPhoneUseCase` on `AppDependencies`. Same response schema; add `email: z.string().nullish()` to `StaffVisitorLookupSchema` (additive for the email endpoint too).
2. **Send the phone as typed (trimmed).** The backend normalises to digits. The client only gates on digit count: `phone.replace(/\D/g, '').length >= 7` and `phone.length <= 50`.
3. **Debounced effect, not blur.** Mirror the email effect (400 ms, `lastLookedUpPhoneRef` keyed on the digits-only value so formatting changes don't re-fire, stale-response guard comparing the current phone). Debounce satisfies "don't fire on every keystroke" and needs no new field wiring.
4. **Fill only empty fields.** Extract a helper `applyLookupMatch(current, match)` that sets each primary-contact field only when it is empty (`''`/unset). Files: set photo / ID proof refs only if no ref is already present. Use it for both lookups. This changes email-lookup behaviour (it previously overwrote name); the spec requirement covers both, and the email lookup's own trigger field is untouched since it is non-empty by definition.
5. **Null-safe ID proof.** `idProofUrl` null/absent → skip the file fetch (already the pattern); photo likewise.
6. **Silent failures.** `null`, 422, network errors are swallowed, as for email. The success toast only shows when something was actually prefilled.
7. **Avoid double-firing.** After a phone hit fills the email, the email effect would trigger a second lookup. Set `lastLookedUpEmailRef` to the prefilled email (and vice versa for phone) when applying a match.
8. **`X-Branch-ID`: mirror the email lookup and send none.** The email lookup sends no header, and prod's CORS currently rejects `x-branch-id` on invitation calls (known gap). The backend author did not verify enforcement on this route. If a branch error appears on stage, add optional `headers` from the selected branch (as `building-repository.ts` does) — the repository method would take an optional `branchId`.

## Risks / Trade-offs

- [Endpoint not deployed yet] → build against the documented contract; verify on stage after deploy; unit tests mock the use case.
- [Branch error on this route] → see decision 8; failure is silent so the form still works, but prefill would silently not happen. Confirm with backend.
- [Behaviour change to email prefill (no overwrite)] → intended and specified; update any existing tests asserting overwrite.
- [Prefill triggered by partial numbers ≥7 digits that match the wrong person] → only empty fields are filled and reception can edit; toast tells them details were prefilled.
