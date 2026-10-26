## Context

`GET /auth/employees` (`auth/router.py::list_employees`) delegates to
`service.list_employees` and `UserRepository.list_employees_page`, which builds a
`conditions` list shared by the count and page statements. Invitation listings
already expose a `search: str | None = Query(max_length=255)` param, so the name
and bound follow existing convention.

## Goals / Non-Goals

**Goals:**
- Server-side substring search over name, email, and employee code.
- Zero change to response shape or existing params.

**Non-Goals:**
- Searching phone number or designation (not requested; easy to add later).
- Full-text/trigram indexing, relevance ranking, or fuzzy matching.
- The React admin portal UI (separate repo).

## Decisions

- **`ILIKE '%term%'` with escaped wildcards.** Escape `\`, `%`, `_` in the term and
  use `ilike(pattern, escape="\\")`. Alternative: raw pattern like
  `search_active_by_name_or_email` does today; rejected because a visible search
  box lets a user type `%` and match everything.
- **Add one OR-condition to the existing `conditions` list** so the count query
  and page query stay in sync and no join is added (no duplicate rows, nothing
  new for `query-performance.md` §1).
- **Trim in the router/service, treat empty as `None`**, so the repository only
  ever sees a meaningful term.
- **No new index.** Directory sizes per tenant schema are small; a leading-wildcard
  `ILIKE` can't use a btree anyway. Revisit with `pg_trgm` if a tenant grows large.
- **Access model unchanged**: stays on the public, 60/min IP-rate-limited
  endpoint; `search` adds no new data beyond what the listing already returns.

## Risks / Trade-offs

- [Sequential scan on large tenants] → acceptable now; trigram index is a later,
  additive migration.
- [Employee codes/emails are PII-adjacent in query strings] → never log the
  `search` value (`logging-observability.md` §2).
