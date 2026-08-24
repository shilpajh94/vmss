## 1. Baseline

- [x] 1.1 Ran `ddev exec uv run pytest` on the unmodified suite: **345 passed**, matching design.md's expected baseline exactly.
- [x] 1.2 `ruff check .` and `ruff format --check .`: both clean before any change.

## 2. Stages 1-7 (API-01..API-15) — spot-check re-confirmation, design.md's "Re-confirming stages 1-7" decision

- [x] 2.1 Confirmed all four named regression tests still exist and pass:
      `auth/tests.py::test_sync_employee_directory_duplicate_employee_code_in_batch_conflict`,
      `invitations/tests.py::test_create_group_invitation_earlier_visitor_file_not_stored_when_later_invalid`,
      `org_structure/tests.py`'s provision-rollback test, and
      `identity_verification/tests.py::test_otp_and_rate_limit_state_are_isolated_per_tenant`.
- [x] 2.2 Full suite (task 1.1) was green and all four regression tests
      pass individually — stages 1-7 (API-01..API-15) confirmed without
      re-deriving their matrix.

## 3. Stage 8 — SSO Login (`sso`, API-19) — design.md's matrix rows S1-S11

- [x] 3.1 Added `test_get_config_requires_permission` (row S1).
- [x] 3.2 Added `test_config_test_connection_requires_permission` (row S3).
- [x] 3.3 Added `test_create_role_mapping_requires_permission` (row S5) —
      distinct from the list-endpoint denial test.
- [x] 3.4 Added `test_delete_role_mapping_requires_permission` and
      `test_delete_role_mapping_not_found` (row S6).
- [x] 3.5 Added `test_logout_writes_audit_entry` and
      `test_logout_requires_authentication` to `auth/tests.py` (row S10,
      colocated with the endpoint's own router/tests, matching this repo's
      per-feature test-file convention).
- [x] 3.6 Split `test_sso_config_and_role_mappings_are_tenant_isolated`
      (row S11) into `test_sso_provider_is_tenant_isolated` and a new
      `test_sso_role_mapping_is_tenant_isolated` that actually creates and
      checks a `SsoRoleMapping` row — the original name promised both but
      only ever checked `SsoProvider`.
      All of Stage 8's new/changed tests plus the full `auth`/`sso` suite
      pass: 80/80 (was 72; +8 new tests, exactly as expected).

## 4. SSRF hardening (design.md's "SSRF guard" decision)

- [x] 4.1 Added `_assert_safe_outbound_url`/`UnsafeDiscoveryUrlError` to
      `oidc_client.py`, called at the top of `fetch_discovery_document`
      (inherited by every caller — `test_client_credentials`, `start_login`,
      `handle_callback`): rejects non-`https` schemes, and rejects a
      resolved host in a private/loopback/link-local/multicast/reserved IP
      range. DNS resolution is offloaded via `anyio.to_thread.run_sync`
      (fastapi-architecture.md §4 — it's blocking I/O) and isolated in
      `_resolve_host_ips` so it's mockable in tests.
- [x] 4.2 New `UnsafeDiscoveryUrlError` type, wired into all three call
      sites: `test_provider_config` (→ `{success: false, message}`),
      `start_login` (→ 503 "SSO provider is currently unreachable" — this
      also fixed a pre-existing gap where `start_login` had no try/except
      around `fetch_discovery_document` at all, so a genuinely unreachable
      IdP at login-initiate time would have surfaced as a raw unhandled 500
      instead of a clean 503), and `handle_callback` (added to its existing
      exception tuple, same generic login-failure path as the other
      verification failures).
- [x] 4.3 Added `test_config_test_connection_rejects_non_https_scheme` and
      `test_config_test_connection_rejects_private_ip_ssrf_attempt`, plus an
      autouse `_stub_dns_resolution` fixture (defaults every test to a safe
      public IP, since none of the existing fake `*.example.com` discovery
      hosts actually resolve) that the SSRF test overrides per-test to a
      private/reserved address. All 34 `sso/tests.py` tests pass (was 26 →
      34 after both this stage and Stage 8's additions).

## 5. Rate limiting (design.md's "Rate limiting" decision)

- [x] 5.1 Added `@limiter.limit("3/minute")` (plus the `request: Request`
      parameter `slowapi` requires) to `GET /auth/sso/{tenant_slug}/login`,
      `GET /auth/sso/callback`, and `POST /auth/sso/exchange` in
      `sso/router.py`, matching `POST /auth/login`'s threshold.
- [x] 5.2 Added `test_login_initiate_rate_limit_trips`,
      `test_callback_rate_limit_trips`, `test_exchange_rate_limit_trips` —
      same `monkeypatch.setattr(limiter, "enabled", True)` pattern as
      `auth/tests.py::test_login_rate_limit_trips`. All 85 `auth`+`sso`
      tests pass (was 80).
- [x] 5.3 Updated `docs/features/sso_authentication.md`: added a rate-limit
      column to the endpoint table, and a new "SSRF guard on admin-supplied
      discovery URLs" subsection documenting the Stage 4 fix.

## 6. Closing gate

- [x] 6.1 `ruff check .` and `ruff format --check .`: clean (one violation
      found and fixed along the way — see 6.2).
- [x] 6.2 `mypy` on `core/`, `auth/`, `sso/`: found and fixed one real type
      error (`socket.getaddrinfo`'s sockaddr tuple typed `str | int`,
      fixed with an explicit `str(...)` in `_resolve_host_ips`). Clean
      after the fix — 33 source files checked, no issues.
- [x] 6.3 Full `ddev exec uv run pytest`: **358 passed**, zero failures —
      grew from the 345 baseline by exactly the 13 new tests added across
      Stages 3-5 (8 Stage-8 gap tests + 2 SSRF tests + 3 rate-limit tests).
- [x] 6.4 Closing summary written below (in the apply-session response).
- [x] 6.5 No `git add`/`git commit` run — working tree left for the user's
      own review and explicit commit instruction.
