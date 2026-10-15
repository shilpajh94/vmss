## 1. Schema and service

- [x] 1.1 Add `DeviceApprovalStatusOut` (`device_id`, `approval_status`, `is_active`, computed `approved`) to `devices/schemas.py`
- [x] 1.2 Add `service.get_device_approval_status(tenant_db, device_id)` using `DeviceRepository.get_by_device_id`; raise 404 `Device not found` when absent

## 2. Router

- [x] 2.1 Add public `GET /devices/approval-status` in `devices/router.py`, declared before the `/{device_pk}` routes, with required `deviceId` query (`min_length=1`, `max_length=255`), `track_default_tenant_db`, `@limiter.limit("60/minute")`, `response_model=Envelope[DeviceApprovalStatusOut]`, `-> JSONResponse`
- [x] 2.2 Confirm no bearer dependency and no audit/background task is attached

## 3. Tests (`devices/tests.py`)

- [x] 3.1 Pending, approved+enabled, and approved+disabled devices return the expected `approvalStatus`/`isActive`/`approved`
- [x] 3.2 Unknown and soft-deleted `deviceId` return 404 and create nothing
- [x] 3.3 Missing/empty `deviceId` returns 422; 429 after exceeding the limit
- [x] 3.4 Endpoint works without an Authorization header and the route does not shadow `GET /devices/{device_pk}`
- [x] 3.5 Camel-case response schema renders in OpenAPI (`tests/test_api_documentation.py` stays green)

## 4. Docs and checks

- [x] 4.1 Document the endpoint (params, responses, rate limit) in `docs/features/devices.md`
- [x] 4.2 Run `ruff check`, `ruff format --check`, and `ddev exec uv run pytest`
