## 1. Repository

- [x] 1.1 Add `InvitationRepository.get_latest_for_prefill_by_email(email:
      str, branch_scope: BranchScope) -> Invitation | None`
      (`src/vmss_api/invitations/repository.py`) — case-insensitive match
      via `func.lower(Invitation.primary_contact_email) ==
      func.lower(email)` (or a bound literal lower-cased in Python, whichever
      matches this file's existing style), `Invitation.deleted_at.is_(None)`,
      `_branch_filter(branch_scope)` applied the same way
      `list_invitations_page` does, `ORDER BY created_at DESC LIMIT 1`. A
      new method, not a change to `get_latest_by_primary_contact_email`
      (design.md "A new repository method...").

## 2. Schema

- [x] 2.1 Add `InvitationLookupPrefillOut(CamelModel)`
      (`src/vmss_api/invitations/schemas.py`): `full_name: str`,
      `phone: str | None`, `preferred_contact_method: str`,
      `visitor_category_id: uuid.UUID | None`, `id_proof_type: str | None`.
      No `id_proof_url`/`photo_url` (design.md Non-Goals).

## 3. Service Layer

- [x] 3.1 Add `service.get_prefill_by_email(tenant_db, email, branch_scope)
      -> InvitationLookupPrefillOut | None` — calls the new repository
      method, returns `None` on no match, otherwise maps the invitation's
      columns onto `InvitationLookupPrefillOut`.

## 4. Router

- [x] 4.1 Add `GET /invitations/lookup-by-email`
      (`src/vmss_api/invitations/router.py`), `response_model=
      Envelope[InvitationLookupPrefillOut | None]`, taking `email:
      Annotated[EmailStr, Query()]`, `tenant_db` via `get_tenant_db`, and a
      `BranchScope` via `require_branch_scope("invitations:create")`
      (mirroring `list_invitations`'s pattern), calling
      `service.get_prefill_by_email` and returning
      `success_response(data=result)` (where `result` may be `None`).

## 5. Tests

- [x] 5.1 Happy path: a caller with `invitations:create` at the matching
      branch gets the most recent invitation's prefill data.
- [x] 5.2 Case-insensitivity: querying with different casing than the
      stored `primary_contact_email` still matches.
- [x] 5.3 No match: an email with no invitation at any authorized branch
      returns `200` with `data: null`.
- [x] 5.4 Branch isolation: a match at a branch the caller is not
      authorized for returns `data: null`, not that branch's data
      (`testing-standards.md` §2's tenant-isolation-style case, scoped to
      branch here).
- [x] 5.5 `X-Branch-ID` narrowing: an explicit header excluding the
      matching branch returns `data: null` even though the caller is
      authorized at the branch that does have a match.
- [x] 5.6 Permission-denied: a caller holding only `invitations:view` (not
      `invitations:create`) gets `403` (`testing-standards.md` §2).
- [x] 5.7 Response shape: assert the response never includes `idProofUrl`
      or `photoUrl` keys.

## 6. Documentation

- [x] 6.1 Add the new endpoint to `docs/features/invitations.md`'s endpoint
      table/description, including the permission, branch-scoping
      behavior, and the `data: null`-on-no-match convention.

## 7. Verification

- [x] 7.1 `ddev exec uv run pytest src/vmss_api/invitations/tests.py`
      passes. (All 7 new tests pass; 305/306 pre-existing tests pass — 1
      pre-existing, unrelated failure confirmed via `git stash` to fail
      identically without this change:
      `test_get_invitation_detail_includes_id_proof_url_with_documents_view`,
      a co-visitor `idProofUrl`/`documents:view` resolution bug unrelated to
      email lookup. Left untouched — out of scope for this change.)
- [x] 7.2 `ddev exec uv run ruff check` and
      `ddev exec uv run ruff format --check` clean on changed files.
- [x] 7.3 `ddev exec uv run mypy src/vmss_api/invitations/` clean
      (`project-rules.md`'s strict-typing scope covers PII-handling
      modules).
- [x] 7.4 Confirm
      `tests/test_api_documentation.py::test_response_schemas_render_camel_case`
      still passes (new schema renders `fullName`/`preferredContactMethod`/
      `visitorCategoryId`/`idProofType` in camelCase, automatic via
      `CamelModel`).

## 8. Follow-up: add photoUrl/idProofUrl (documents:view-gated)

Scope addition after the frontend saw the first version and asked for
these fields — see proposal.md/design.md's revised Non-Goals and
Decisions.

- [x] 8.1 Add `photo_url: str | None` and `id_proof_url: str | None` to
      `InvitationLookupPrefillOut` (`src/vmss_api/invitations/schemas.py`).
- [x] 8.2 `service.get_prefill_by_email` takes a `user: User` param,
      computes `include_documents = user.has_permission("documents:view",
      invitation.branch_id)`, resolves `photo_url` unconditionally via
      `storage_url_for` and `id_proof_url` only when `include_documents`
      (mirrors `router.py::_to_invitation_detail_out`'s exact pattern —
      design.md "photoUrl unconditional, idProofUrl gated...").
- [x] 8.3 Router passes `user` (already resolvable via
      `Depends(get_current_user)`, cached alongside
      `require_branch_scope`'s own internal use of it) through to the
      service call.
- [x] 8.4 Test: `photoUrl` resolves for a caller who holds
      `invitations:create` but not `documents:view`.
- [x] 8.5 Test: `idProofUrl` is `null` for a caller who holds
      `invitations:create` but not `documents:view` at the matched
      invitation's branch.
- [x] 8.6 Test: `idProofUrl` resolves for a caller who holds both
      `invitations:create` and `documents:view` at that branch.
- [x] 8.7 Remove/replace the now-inaccurate
      `test_lookup_by_email_response_never_includes_document_urls` (task
      5.7) with the three cases above.
- [x] 8.8 Update `docs/features/invitations.md`'s new endpoint row to
      describe the `photoUrl`/`idProofUrl` gating.
- [x] 8.9 Re-run `ddev exec uv run pytest src/vmss_api/invitations/tests.py`,
      `ruff check`/`format --check`, `mypy src/vmss_api/invitations/`, and
      the camelCase regression test.
