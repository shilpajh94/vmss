## Context

See proposal.md - Why. Two independent code paths are touched:
`registrations/deps.py::get_registration_device` /
`_resolve_default_device_context` (shared by all four endpoints in scope,
via `visit_info/router.py`'s `Depends(get_registration_device)` /
`Depends(get_registration_tenant_db)`), and
`visit_info/router.py::search_hosts` +
`visit_info/service.py::search_hosts`.

## Goals / Non-Goals

**Goals:**
- Make the walk-in "no default tenant/branch configured" failure mode
  loud (ERROR-level, distinct message) instead of indistinguishable from a
  bad device key.
- Let `GET /hosts/search` be called with no `query` and get a useful,
  bounded response instead of a 422.
- Close the test-coverage gap that let "device key is already optional on
  these three endpoints" go unverified.

**Non-Goals:**
- Changing the 401 status code, the fallback-to-default-tenant/branch
  mechanism itself, or anything about how a *valid* device key resolves —
  none of that is broken.
- Fixing the `vmss-dev` `.env` placeholder values — that's an environment
  action item (proposal.md - Impact), not something this change's code can
  do.
- Any change to `/visit-info/departments` or `/visit-info/options` beyond
  adding regression tests — investigation found no mandatory-device-key
  code path on either.
- Ranking or relevance-scoring the browsable default list beyond
  alphabetical order.

## Decisions

**Split the 401 message/log-level by cause, keep the status code.**
Both failure causes remain 401 (no registration should be created against
an unresolved branch either way), but `_resolve_default_device_context`
raises with a distinct detail string and logs at `ERROR` when the default
tenant/branch itself is the problem, while the existing invalid-key path
in `get_registration_device` keeps its current `WARNING` + message.
Alternative considered: return 500 for the misconfiguration case (arguably
more semantically correct — the *server* is broken, not the request) but
rejected because the existing spec and tests already commit to 401 for
"no usable tenant/branch was resolved," and changing the status code is a
larger, less-obviously-safe contract change than changing message text for
a documented-as-not-versioned field (`api-conventions.md` §2 treats status
code changes as breaking; message text is not enumerated as part of the
contract).

**`query` omitted/blank on `/hosts/search` reuses the search code path with
an empty filter, not a separate "list all hosts" branch.**
`visit_info/service.py::search_hosts` already does a `WHERE name ILIKE ...
OR email ILIKE ...`-style match; when `query` is empty, the service issues
the same query shape with no filter clause (or a `TRUE` filter), ordered by
name, reusing existing pagination/limit logic. Alternative considered: a
distinct `list_hosts` service method — rejected as unnecessary duplication
per `project-rules.md`'s "no premature abstraction," since the only
difference is whether a `WHERE` clause is applied, not the query shape,
ordering, or response schema.

**Router change: drop `Query(min_length=2)` with no default for `str |
None`, validate the minimum length in the service/router body instead.**
FastAPI's `Query(min_length=...)` only applies when a value is present, so
switching the param to `Annotated[str | None, Query()] = None` and doing
the "supplied but too short → 422" check explicitly (mirroring how other
endpoints in this codebase validate conditionally-required query params)
keeps the validation-error behavior for a too-short query while allowing
`None`/blank through.

## Risks / Trade-offs

[Omitting `query` on a public, unauthenticated endpoint now returns the
full active-employee directory (paged by `limit`)] → Mitigation: this is
already the resolved-tenant's employee directory the endpoint was designed
to search across with a 2-character query; the browsable list is capped at
the same `limit`/`_MAX_LIMIT` (25) as a normal search and carries no more
PII per row than a search result already does (`id`/`name`/`email`/
`department`). No new data exposure, only a lower bar to see the first
page of it — the same trust boundary the endpoint already operates in
(`security-architecture.md` §2's public-endpoint posture, unchanged rate
limit).

[Changing the "Missing or invalid device credential" 401 message text
could break a frontend integration that pattern-matches the exact string]
→ Mitigation: message text is documented as non-contractual
(`api-conventions.md` §2); flag the two new message strings to the
frontend team explicitly when this ships, same as any other message-copy
change.

## Migration Plan

No data migration. Deploy as a normal code change; no rollback concerns
beyond reverting the commit. The `.env` action item (proposal.md - Impact)
is independent and can land before, with, or after this code change — the
code fix makes the failure mode visible/loud regardless of when the
environment config is corrected.
