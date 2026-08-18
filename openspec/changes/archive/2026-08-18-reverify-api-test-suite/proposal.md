## Why

Two changes landed since the last full test run reported in this session
(`audit-and-expand-api-test-coverage`, which left the suite at 189 passing):
the initial repo commit, and `adopt-env-example-placeholder-tokens` (which
touched `.env.example`/`README.md` only). Before trusting that state, re-run
the full suite once more to confirm every feature's API endpoints still pass
with nothing silently broken by the intervening changes.

## What Changes

- Re-run the full `ddev exec uv run pytest` suite across all 7 feature
  routers (`auth`, `invitations`, `org_structure`, `platform`, `reports`,
  `tenant`, `visitors`) and report the pass/fail count.
- If everything passes, confirm the total matches the last known-good count
  (189) — a lower total without an explanatory code change would itself be a
  signal worth investigating, not just reporting.
- If anything fails, stop and report the specific failure(s) rather than
  re-running or working around them — this change's scope is verification,
  not fixing (see design.md).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — running the existing test suite doesn't change any spec-level
behavior. This change sets `skip_specs: true` in `.openspec.yaml`
accordingly.

## Impact

- **Affected code**: none planned. This is a read-only verification pass.
- **No dependency, schema, or API changes.**
