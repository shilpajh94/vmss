## 1. Permissions and Model

- [x] 1.1 Add `kiosks:manage` and `kiosks:view` to `PERMISSION_CODES` in `auth/rbac_catalog.py` and confirm how existing tenants receive new permissions
- [x] 1.2 Create `src/vmss_api/kiosks/__init__.py` and `models.py` with `Kiosk` (incl. partial unique index on `lower(name)`)
- [x] 1.3 Register the model where tenant metadata is imported so `Base.metadata` and Alembic see it
- [x] 1.4 Add tenant Alembic migration for `kiosks` (single head) and verify upgrade/downgrade

## 2. Schemas, Repository, Service

- [x] 2.1 `schemas.py`: `KioskCreate`, `KioskUpdate`, `KioskVisibilityUpdate`, `KioskOut`, sort-field Literal (all `CamelModel`)
- [x] 2.2 `repository.py`: `KioskRepository(TenantScopedRepository)` with `list_page` (status, includeHidden, sort, pagination), name-exists check, soft delete
- [x] 2.3 `service.py`: create/get/update/set_visibility/delete with 404 and duplicate-name 409 handling

## 3. Router and Wiring

- [x] 3.1 `router.py`: six endpoints with `require_permission`, `response_model`, `-> JSONResponse`, and background audit entries
- [x] 3.2 Register in `api.py`; add `kiosks` tag with description to `_TAGS_METADATA` in `main.py`

## 4. Tests and Docs

- [x] 4.1 `tests.py`: happy path for every endpoint, hide/unhide list behavior, duplicate name, deleted-name reuse
- [x] 4.2 Permission-denied (403), unauthenticated (401), and tenant-isolation tests
- [x] 4.3 Add `docs/features/kiosks.md`; run `ruff check`, `ruff format --check`, `pytest` (incl. `tests/test_api_documentation.py`)
