## 1. Token Validation

- [x] 1.1 Add a `verified_contact` FastAPI dependency (new
      `src/vmss_api/visitor_return_visit/deps.py`) that calls
      `core/security.py::decode_token`, rejects with 401 if
      `claims["type"] != "identity_verified"`, and returns the identifier
      (`sub`) and `channel` claim.
- [x] 1.2 Unit-style test: a valid `identity_verified` token is accepted and
      its identifier/channel extracted.
- [x] 1.3 Unit-style test: a missing, expired, tampered, or wrong-`type`
      (e.g. a staff access token) token is rejected with 401.

## 2. Repository (Read-Only Prior-Visit Lookup)

- [x] 2.1 Create `src/vmss_api/visitor_return_visit/repository.py` with a
      query for the most recent non-deleted `Invitation` whose
      `primary_contact_email` or `primary_contact_phone` matches the given
      identifier, and a paginated query for all such matches ordered
      newest-first (`query-performance.md` §1 — no N+1, single indexed
      `WHERE`/`ORDER BY`/`LIMIT`).
- [x] 2.2 Confirm/add a DB index on `Invitation.primary_contact_email` and
      `Invitation.primary_contact_phone` if not already present, so this
      lookup doesn't scan.
- [x] 2.3 Test: an identifier with multiple prior visits returns them
      newest-first; an identifier with none returns an empty result (not an
      error).
- [x] 2.4 Test: a different identifier's visits are never returned for the
      identifier being looked up (tenant-isolation-style test per
      `testing-standards.md` §2, scoped to contact matching rather than
      schema).

## 3. Schemas

- [x] 3.1 Add `schemas.py` (`CamelModel` subclasses):
      `VisitHistoryEntry` (trackingId, status, visitDate, purpose),
      `ReturningVisitorPrefill` (fullName, email, phone,
      preferredContactMethod, idProofType, idProofUrl, photoUrl — field
      names matching the resolved-URL naming already used elsewhere in
      this API, not the dynamic registration form's own field keys, since
      the consuming client has its own fixed mapping onto that form),
      `ReturningVisitorLookupOut` (history: list,
      prefill: ReturningVisitorPrefill | None, plus a `pagination` field per
      `api-conventions.md` §1).

## 4. Service Layer

- [x] 4.1 Add `service.py::get_returning_visitor_data(identifier,
      tenant_id)` that resolves the default tenant's schema, queries the
      repository, and shapes the response — prefill absent (null) when no
      prior visit exists.
- [x] 4.2 Reuse `core/tenancy.py::resolve_default_tenant` for tenant
      resolution; on `DefaultTenantUnresolved`, log at `ERROR` distinguishing
      "no such tenant" vs. "inactive", matching `registrations`/
      `identity_verification`'s existing pattern.

## 5. Router

- [x] 5.1 Add `router.py` with `GET /visitor-portal/me` (or equivalent),
      `Depends(verified_contact)`-gated, `response_model=Envelope[...]` per
      `api-documentation.md` §1, returning `success_response(data=...)`.
- [x] 5.2 Apply `slowapi` rate limiting per client IP, matching
      `identity-verification`'s existing posture.
- [x] 5.3 Register the router: `api.py` include, `main.py` `_TAGS_METADATA`
      entry (`api-documentation.md` §2).

## 6. Logging

- [x] 6.1 Bind `request_id`/`tenant_id` context per
      `logging-observability.md` §1; log the identifier in masked form only,
      consistent with `identity-verification`'s existing masking helper
      (`identity_verification/masking.py`) — reuse it rather than
      reimplementing.

## 7. Tests

- [x] 7.1 Endpoint test: valid proof token with prior visits returns history
      + prefill.
- [x] 7.2 Endpoint test: valid proof token with no prior visits returns
      empty history and null prefill, 200 (not 404).
- [x] 7.3 Endpoint test: missing/invalid/expired/wrong-type token rejected
      with 401.
- [x] 7.4 Endpoint test: prefill payload includes a fetchable `idProofUrl`
      for the underlying invitation's own ID-proof document when one is on
      file, and `null` (not omitted) when one is not.
- [x] 7.5 Endpoint test: rate limit trips return 429 consistent with other
      public endpoints.
- [x] 7.6 Regression test confirming `POST /registrations/walk-in` and
      `POST /invitations` behavior is completely unchanged by this addition.

## 8. Documentation

- [x] 8.1 Add `docs/features/visitor_return_visit.md` (matching the
      existing `identity_verification.md`/`visit_info.md` underscore
      naming) describing the endpoint(s), the proof-token contract, and the
      prefill/history response shape.
