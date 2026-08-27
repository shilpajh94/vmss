## 1. Data Model & Migrations

- [x] 1.1 Add `VisitPurpose` and `VisitDuration` models to
      `src/vmss_api/visit_info/models.py` (`Base`/`TimestampMixin`, soft
      `deleted_at`, `is_active`, `sort_order`; `VisitDuration` also gets
      `minutes: int`).
- [x] 1.2 `alembic_tenant/` migration: create `visit_purposes` and
      `visit_durations` tables.
- [x] 1.3 `alembic_tenant/` data migration: seed `visit_purposes` (Business
      Meeting, Job Interview, Delivery / Pickup, Personal Visit, Vendor /
      Contractor Work, Other) and `visit_durations` (30 minutes/30, 1 hour/60,
      2 hours/120, Half day (4 hours)/240, Full day/480) with `sort_order`
      matching this listing order.
- [x] 1.4 Add nullable `purpose_id`, `host_id` (→ `users.id`), `duration_id`,
      `department_id` FK columns to `invitations/models.py::Invitation`.
- [x] 1.5 `alembic_tenant/` migration for the four new `Invitation` FK
      columns.

## 2. Repository Additions (owning features)

- [x] 2.1 `auth/repository.py::UserRepository`: add
      `search_active_by_name_or_email(query, limit)` (case-insensitive
      `ILIKE` on `full_name`/`email`, `is_active = True`, joins/loads
      `department_id`'s name via `selectinload`/explicit join per
      `query-performance.md` §1). (Department name resolution is batched in
      `visit_info/service.py` instead — one extra query, not a join, since
      `Department` isn't a relationship on `User`.) Also added `get_active`
      for id-validation (task 6).
- [x] 2.2 `org_structure/repository.py::DepartmentRepository`: add
      `list_active_for_branch(branch_id)` (active, non-deleted, no
      pagination — kiosk dropdown needs the full set). Also added
      `get_names_by_ids` (batched host-department-name lookup) and
      `get_active` (id-validation, task 6).
- [x] 2.3 `visit_info/repository.py`: `VisitPurposeRepository`,
      `VisitDurationRepository` — each a `list_active()` ordered by
      `sort_order`.
- [x] 2.4 `visit_info/repository.py`: lookup-by-id methods for
      `VisitPurpose`/`VisitDuration` used by id-validation in task 6.

## 3. `visit_info` Schemas

- [x] 3.1 `visit_info/schemas.py`: `HostSearchResultOut` (`id`, `name`,
      `email`, `department: str | None`), `HostSearchOut` (`hosts: list[...]`).
- [x] 3.2 `DepartmentLookupOut` (`id`, `name`), `DepartmentLookupListOut`
      (`departments: list[...]`).
- [x] 3.3 `VisitPurposeOut` (`id`, `name`), `VisitDurationOut` (`id`, `name`,
      `minutes`), `VisitInfoOptionsOut` (`purposes: list[...]`,
      `durations: list[...]`).
- [x] 3.4 All extend `CamelModel`; all response models registered via
      `response_model=Envelope[...]` on their routes (`api-documentation.md`
      §1).

## 4. `visit_info` Service Layer

- [x] 4.1 `visit_info/service.py::search_hosts(tenant_db, query, limit)` —
      calls `UserRepository.search_active_by_name_or_email`, maps to
      `HostSearchResultOut` (resolving each `department_id` to a name via one
      batched query, not one query per host — `query-performance.md` §2).
- [x] 4.2 `visit_info/service.py::list_departments(tenant_db, branch_id)` —
      calls `DepartmentRepository.list_active_for_branch`.
- [x] 4.3 `visit_info/service.py::get_visit_info_options(tenant_db)` — calls
      both catalog repositories, assembles `VisitInfoOptionsOut`.

## 5. `visit_info` Router

- [x] 5.1 `visit_info/router.py`: `GET /hosts/search` — `query: str =
      Query(min_length=2)`, `limit: int = Query(default=10, ge=1, le=25)`,
      depends on `registrations.deps.get_registration_tenant_db` (tenant
      only), `@limiter.limit("20/minute")`.
- [x] 5.2 `GET /visit-info/departments` — depends on
      `registrations.deps.get_registration_device` (for `branch_id`) +
      `get_registration_tenant_db`, `@limiter.limit("20/minute")`.
- [x] 5.3 `GET /visit-info/options` — depends on
      `registrations.deps.get_registration_tenant_db`,
      `@limiter.limit("20/minute")`.
- [x] 5.4 Register `visit_info.router.router` in `api.py`; add its tag +
      description to `main.py`'s `_TAGS_METADATA` (`api-documentation.md`
      §2).

## 6. Invitation Id-Field Integration

- [x] 6.1 `invitations/schemas.py::VisitDetailsSubmit`: add optional
      `purpose_id`, `host_id`, `duration_id`, `department_id`
      (`uuid.UUID | None`).
- [x] 6.2 `invitations/service.py`: when an id is present, resolve it
      (`VisitPurposeRepository`/`UserRepository`/`VisitDurationRepository`/
      `DepartmentRepository`, all scoped to the same `tenant_db`), reject with
      a validation error if it doesn't resolve to an active row, and
      overwrite the paired free-text field with the resolved row's canonical
      name/`full_name` before constructing the `Invitation` row. Persist the
      id itself in the new FK column.
- [x] 6.3 Confirm `registrations/schemas.py`'s re-export of
      `VisitDetailsSubmit` needs no change (it imports the class directly) —
      add a one-line comment/test asserting the walk-in schema exposes the
      new fields, so a future refactor that breaks the re-export is caught.

## 7. Tests (`testing-standards.md` §2)

- [x] 7.1 `visit_info/tests.py`: happy path for each of the 3 endpoints.
- [x] 7.2 Host search: query-too-short (422), empty-result (200, `[]`),
      `limit` capping, deactivated employee excluded.
- [x] 7.3 Department listing: cross-branch isolation (branch A's departments
      never appear when resolved branch is B), inactive/deleted excluded.
- [x] 7.4 Visit-info options: seeded purposes/durations returned with correct
      `minutes` values and `sort_order`.
- [x] 7.5 Rate-limit test for at least one of the 3 endpoints (429 beyond
      `20/minute`), following the existing pattern for
      `POST /registrations/walk-in`.
- [x] 7.6 `invitations/tests.py` (or equivalent): submission with no ids
      (unchanged behavior), submission with a valid id (free-text overwritten
      with canonical value), submission with an unknown/cross-tenant id
      (rejected, nothing created).
- [x] 7.7 `registrations/tests.py`: at least one walk-in submission test using
      the new optional id fields, confirming identical resolve/overwrite
      behavior to invitations.
- [x] 7.8 Tenant-isolation case per `testing-standards.md` §2: a
      `purpose_id`/`department_id` valid in one tenant's schema is rejected
      when submitted against a different tenant.

## 8. Documentation

- [x] 8.1 Add `docs/features/visit_info.md` describing the three endpoints,
      the device-credential resolution/fallback, and the seeded catalog
      contents.
- [x] 8.2 Update `docs/features/invitations.md` (and/or `registrations.md`)
      noting the new optional id fields on `VisitDetailsSubmit`.
