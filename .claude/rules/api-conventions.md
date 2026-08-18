---
trigger: model_decision
description: Apply when designing or modifying a list/collection endpoint, making a breaking change to an existing endpoint or schema, or building a mutating endpoint that a mobile/web client may retry (check-in/out, invitation creation, OTP verify).
---

# API Conventions — VMSS_API

Covers three concerns that `fastapi-architecture.md` doesn't: how list endpoints
expose pagination/filtering/sorting, how breaking changes get versioned, and how
retry-prone mutations avoid double-processing.

## 1. Pagination, Filtering, Sorting (list endpoints)

- **Pagination**: `page` (1-indexed) + `page_size` (default 20, hard max 100) query
  params, validated on the request schema — not raw `int` params on the route
  function. Response envelope nests pagination metadata inside the existing
  `success_response` shape:
  ```json
  {"data": [...], "pagination": {"page": 1, "pageSize": 20, "total": 143, "totalPages": 8}}
  ```
  Use limit/offset, not cursor pagination — VMSS list views (visitors, audit logs,
  reports) are paged by humans clicking "next", not streamed by another service;
  cursor pagination is complexity this doesn't need yet.
- **Filtering**: each filterable field is an explicit, typed query param on the
  endpoint's query schema (e.g. `status: VisitorStatus | None`, `checked_in_after:
  datetime | None`) — never a generic `?filter=` string the service has to parse.
  Explicit params are what makes a filter show up in the OpenAPI docs and get
  Pydantic validation for free.
- **Sorting**: `sort_by` + `sort_order` (`asc`/`desc`), where `sort_by` is validated
  against an explicit whitelist of sortable columns per endpoint (an `Enum` or
  `Literal[...]`) — never pass the raw string into `order_by()`. An unvalidated
  sort column is a minor SQL-injection-adjacent footgun and also lets a client sort
  by a column that isn't indexed.

## 2. API Versioning & Deprecation

- Today there's exactly one version, mounted at `/api/v1` (`fastapi-architecture.md`
  §7). Additive changes — a new optional response field, a new endpoint, a new
  optional request param — ship into `v1` directly, no version bump needed.
- A **breaking change** — removing/renaming a field, changing a field's type or
  semantics, tightening validation on an existing param, changing what status code
  an endpoint returns for the same condition — requires a new prefix (`/api/v2` for
  that resource) rather than mutating `v1`'s contract under existing clients. The
  React portal and Flutter app are separate repos on their own release cadences;
  they can't be assumed to redeploy in lockstep with the API.
- A deprecated endpoint gets a `Deprecation` response header and a note (with a
  target removal date) in its `docs/features/<feature>.md` file — not a silent
  removal. Give both client teams a window to migrate before deleting the old path.

## 3. Idempotency for Mutating Endpoints

- Endpoints a flaky mobile network causes legitimate retries on — check-in/out,
  invitation creation, OTP verify/request, any "do this exactly once" action — must
  accept an `Idempotency-Key` header.
- Server-side: on first request, process normally and cache
  `(idempotency_key, tenant_id) -> response` in Redis for ~24h
  (`vmss:{tenant_id}:idempotency:{key}`, consistent with the key convention
  in `database-architecture.md` §6). On a retried request with the same key, return
  the cached response without re-executing the mutation.
- Without this, a visitor whose check-in request times out and retries on a bad
  connection can end up checked in twice, which corrupts the "who's inside" report
  that the emergency feature depends on.
