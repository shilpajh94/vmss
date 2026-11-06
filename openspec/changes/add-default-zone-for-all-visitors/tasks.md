## 1. Model and migration

- [x] 1.1 Add `Zone.is_default` (`Mapped[bool]`, default false) and the partial unique index `uq_zone_branch_default` in `access_control/models.py`
- [x] 1.2 Add one tenant migration in `alembic_tenant/versions/` adding the column (server default false) and the index, with downgrade; confirm it applies on a fresh and an existing tenant schema

## 2. Schemas and zone management

- [x] 2.1 Add `is_default` to `ZoneCreate`, `ZoneUpdate` (optional) and `ZoneOut`; add an `is_default` list filter
- [x] 2.2 In the zone repository/service, set default atomically (clear the branch's previous default, set the new one), 422 if the zone is inactive/deleted, one audit entry with old/new default ids
- [x] 2.3 Return 409 when deleting or deactivating the current default zone

## 3. Effective allowed zones

- [x] 3.1 Add a repository method returning the branch's live, active default zone id (one query)
- [x] 3.2 Change `effective_zone_ids` to take `branch_id` and union the default zone into the result
- [x] 3.3 Update both callers (`access_control/service.py` scan loader, `access_control/checkin_gate.py`) to pass the visit's `branch_id`

## 4. Tests (`access_control/tests.py`)

- [x] 4.1 Decision/resolver cases: no assignment + default (allow), no assignment + no default (deny), explicit list keeps default, other-branch default ignored, inactive default ignored
- [x] 4.2 Scan and front-desk check-in: default zone allowed with no assignment; unapproved/blacklisted/expired visit still denied
- [x] 4.3 Management: set/clear/replace default, one-per-branch index, 409 on delete/deactivate default, 422 inactive, `isDefault` filter
- [x] 4.4 Permission-denied (`zones:manage`) and tenant-isolation case for the new write path; toggle-off returns 404

## 5. Docs and verification

- [x] 5.1 Update `docs/features/access_control.md` (default-deny paragraph, zone endpoints, `isDefault`)
- [x] 5.2 Run targeted tests only: `access_control` tests, `tests/test_api_documentation.py`, and the invitations check-in tests (consumer of `checkin_gate`); one sequential `ddev exec uv run pytest <paths>`; run `ruff check` and `ruff format --check`
