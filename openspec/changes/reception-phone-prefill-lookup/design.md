## Context

See proposal.md - Why. `GET /invitations/lookup-by-email` (archived change `add-invitation-lookup-by-email`) already established the staff prefill pattern: `require_branch_scope("invitations:create")`, a purpose-built repository query, `data: null` on no match, and `idProofUrl` gated on `documents:view`. `Invitation.primary_contact_phone` is a free-text `String(50)` with a plain index. Phones are stored exactly as submitted, with no normalization anywhere in the codebase. The existing exact-match phone queries (`get_latest_by_primary_contact_phone`, `VisitorReturnVisitRepository._contact_filter`) back other flows and must not change.

## Goals / Non-Goals

**Goals:**
- A staff, branch-scoped phone lookup that returns name, email and the other prefill fields.
- Tolerate formatting differences in stored and typed phones.

**Non-Goals:**
- No change to the OTP-gated visitor portal prefill, which works as is.
- No change to dedupe-on-create behavior or the existing exact-match phone queries.
- No rewrite or backfill of stored phone values.
- No new permission, and no country-code inference (a number typed without country code does not match one stored with it).

## Decisions

**Sibling endpoint `/invitations/lookup-by-phone`, not a merged `/lookup?email=|phone=`.** Keeps the shipped email endpoint's contract untouched, and keeps each filter an explicit typed param (`api-conventions.md` §1). Alternative of one polymorphic endpoint rejected because it forces the client to change an existing call.

**Reuse permission and branch scoping from the email lookup.** `require_branch_scope("invitations:create")`, same `documents:view` gate for `idProofUrl`. The service's prefill-building code is extracted into a shared helper so both lookups return identical shapes.

**Digits-only comparison via SQL, not Python.** The repository filters on `regexp_replace(primary_contact_phone, '\D', '', 'g') = :digits`, with the input normalized the same way by a small shared helper. Alternative of normalizing at write time needs a backfill and touches create/edit paths, which is far wider than this feature needs.

**Functional index.** Add an `alembic_tenant` migration creating an index on that same expression, since the plain index on `primary_contact_phone` cannot serve it. The query expression and the index expression must match exactly.

**Add `email` to `InvitationLookupPrefillOut`.** One shared schema, additive optional field, so the email lookup gains it harmlessly.

**Minimum 7 digits.** Prevents trivially short inputs from matching an arbitrary visitor while the user is still typing. Validated on the query param.

## Risks / Trade-offs

- [Same number stored with and without country code won't match] → Documented limitation; revisit with an E.164 normalization change if reception hits it.
- [Staff can enumerate visitor PII by phone] → Same exposure as the email lookup: requires `invitations:create`, branch-scoped, `idProofUrl` gated. Log at `INFO` with the phone masked (`mask_identifier`), never the raw value.
- [Functional index requires a tenant migration across all schemas] → Standard `alembic_tenant` rollout via the existing upgrade path; the query is correct without the index, only slower.
- [Multiple different people share one phone] → Most recent invitation wins, same as the email lookup.
