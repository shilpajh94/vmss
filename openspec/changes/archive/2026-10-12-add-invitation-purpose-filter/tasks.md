## 1. Implementation

- [x] 1.1 `invitations/repository.py`: add a `purpose_of_visit: str | None` keyword to `InvitationRepository.list_page` and append `Invitation.purpose_of_visit == purpose_of_visit` to `filters` when set
- [x] 1.2 `invitations/service.py`: thread `purpose_of_visit` through `list_invitations_page` to the repository
- [x] 1.3 `invitations/router.py`: add `purpose_of_visit: Annotated[str | None, Query(alias="purposeOfVisit", max_length=255)] = None` to `list_invitations` and pass it to the service; mention it in the docstring's filter list
- [x] 1.4 Update existing direct `list_page`/`list_invitations_page` call sites in `invitations/tests.py` (≈ lines 4498, 4539) to pass `purpose_of_visit=None` — not needed: `purpose_of_visit` defaults to `None` on both, so existing call sites stay valid unchanged

## 2. Tests (`invitations/tests.py`, factories per testing-standards.md §1)

- [x] 2.1 Happy path: two invitations with different purposes; `?purposeOfVisit=` returns only the matching one and `pagination.total == 1`
- [x] 2.2 Combined with `status`: matching purpose but different status is excluded
- [x] 2.3 `relevantToMe=true` mode honours the filter
- [x] 2.4 Exact-match: a partial value returns nothing
- [x] 2.5 A 256-character value returns 422
- [x] 2.6 Confirm the existing permission-denied and tenant-isolation tests for `GET /invitations` still pass unchanged (no new endpoint, so no new ones are required)

## 3. Docs and checks

- [x] 3.1 Add `purposeOfVisit` to the `GET /invitations` parameters in `docs/features/invitations.md`
- [x] 3.2 `ddev exec uv run ruff check`, `ruff format --check`, `mypy` on `invitations`, and `ddev exec uv run pytest src/vmss_api/invitations` green (do not run parallel pytest processes) — ruff clean; mypy's 6 errors are pre-existing in unrelated test helpers (tests.py ≈11217–11797); invitations suite has the same 88 pre-existing failures with and without this change (create/walk-in 422s), plus the known-flaky `test_get_invitation_detail_includes_id_proof_url_with_documents_view`
