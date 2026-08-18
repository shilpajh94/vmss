---
trigger: glob
globs: src/vmss_api/**/repository.py
---

# Query Performance Standards — VMSS_API

`database-architecture.md` mandates the repository pattern; this file covers how
queries inside `repository.py` avoid N+1s once relationships are involved.

## 1. Eager-Load What the Caller Will Access

- If a repository method returns a model whose relationship the service or
  response schema will touch (e.g. an `Invitation` with `.visitor`, a `Role`
  with `.permissions`), load it explicitly in the query with
  `selectinload`/`joinedload` — don't rely on lazy-loading to fetch it later. Async
  SQLAlchemy has no implicit lazy-load fallback outside an active session context,
  so an un-eager-loaded relationship accessed from a Pydantic
  `model_validate(from_attributes=True)` call is a runtime `MissingGreenlet` error
  waiting to happen, not just a performance issue.
  ```python
  stmt = (
      select(Invitation)
      .options(selectinload(Invitation.visitor))
      .where(Invitation.id == id_, Invitation.deleted_at.is_(None))
  )
  ```
  Note there's no tenant WHERE clause to remember here — `session` is already
  bound to one tenant's schema (`database-architecture.md` §2), so the only
  filter this repository needs is the soft-delete one `TenantScopedRepository`
  already applies.
- Use `selectinload` for one-to-many/many-to-many (separate `IN` query, avoids
  result-set fan-out); use `joinedload` for many-to-one/one-to-one (single query,
  no fan-out risk since it's at most one row per parent).

## 2. Never Loop-and-Query

- If a service needs related rows for a list of ids (e.g. approval status for 50
  invitations), that's one repository method issuing a single `WHERE id IN (...)`
  or a joined query — never a loop in the service calling `repository.get(id)`
  once per item. A list endpoint that does 1 query to fetch the page and N queries
  to hydrate each row is the single most common way a "works fine locally"
  endpoint becomes a timeout in staging once a tenant has real data volume.

## 3. Bulk Writes

- Bulk state changes (e.g. bulk-approving a batch of invitations, bulk check-out at
  end of day) use a single `UPDATE ... WHERE id IN (...)` statement, not a loop of
  per-row `session.add()`/`commit()` calls. Commit once per logical operation, not
  once per row.
