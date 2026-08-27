## 1. Code comment cleanup (no behavior change)

- [x] 1.1 In `src/vmss_api/registrations/deps.py::_resolve_default_device_context`,
      rewrite the docstring's "**Known trade-off, not a full fix**" paragraph
      to describe the fallback as the sanctioned default path rather than an
      open item — keep the factual content (it's an unauthenticated write
      against one fixed branch, protected only by rate limiting; the
      OTP-bound follow-up remains a separate future improvement) but drop the
      "trade-off"/"not a full fix" framing that implies it's unreviewed.
- [x] 1.2 In `docs/features/registrations.md`, update the corresponding
      "Known trade-off, not a full fix" section (around the "Fallback when no
      `X-Device-Key` is sent at all" heading) to match — same content, same
      framing change as 1.1.

## 2. Verify existing behavior matches the spec

- [x] 2.1 Confirm `src/vmss_api/registrations/deps.py::get_registration_device`
      already implements every scenario in the modified `registrations` spec
      (no-header fallback success, no-header with unavailable default
      tenant/branch rejected, invalid/inactive credential rejected, valid
      credential resolves tenant/branch) — expected to require no code
      changes, since this change is a spec correction, not a behavior change.
- [x] 2.2 Run `ddev exec uv run pytest src/vmss_api/registrations/tests.py -k device_key`
      and confirm the existing tests
      (`test_walk_in_registration_missing_device_key_falls_back_to_default_tenant_success`,
      `test_walk_in_registration_missing_device_key_no_default_tenant_rejected`,
      `test_walk_in_registration_missing_device_key_no_default_branch_rejected`,
      `test_walk_in_registration_invalid_device_key_rejected`,
      `test_walk_in_registration_inactive_device_key_rejected`) already cover
      every scenario in the modified spec and pass unmodified.

## 3. Close out the change

- [x] 3.1 Run `openspec validate --change make-walkin-device-key-optional --strict`
      and fix any reported issues.
- [x] 3.2 Archive the change once 1.x and 2.x are confirmed, so
      `openspec/specs/registrations/spec.md` picks up the modified
      requirement.
