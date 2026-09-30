## Why

`GET /visitor-portal/me`'s prefill payload (`ReturningVisitorPrefill`) already
pre-fills a returning visitor's full name, email, phone, and ID-proof type
from their most recent prior visit, but omits `visitor_category_id`. The
walk-in registration form's "Visitor Category" field therefore always renders
as an empty "Select category" for a returning visitor, even though the data
needed to pre-select it (the category the visitor registered under last time)
already exists on the source `Invitation` row and requires no new query — the
column is already selected by the existing repository lookup, just not
surfaced in the response schema. This is a data-completeness gap in the
backend response, not a frontend defect.

## What Changes

- Add `visitor_category_id` (nullable UUID) to `ReturningVisitorPrefill`,
  sourced directly from the most-recent invitation's existing
  `visitor_category_id` column — no new query, join, or eager-load needed.
- Follow the id-only convention already used for this field everywhere else
  in the API (`InvitationOut`, `InvitationListItemOut`, etc.): expose the raw
  FK id, not a denormalized category name — the client already loads the
  category picker's options from the existing public `GET /visitor-categories`
  endpoint and can match by id.
- Update `docs/features/visitor_return_visit.md`'s endpoint description and
  the `visitor-return-visit` capability's "Prefill Payload Is Drawn From the
  Most Recent Prior Visit" requirement to list this eighth field.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `visitor-return-visit`: the "Prefill Payload Is Drawn From the Most Recent
  Prior Visit" requirement gains an eighth prefill field, `visitorCategoryId`,
  nullable like the others. Note: this capability's spec has not yet been
  synced from `openspec/changes/visitor-return-visit-login/specs/` into
  `openspec/specs/` (that change is implemented but not yet archived) — this
  delta targets the same capability path so it applies cleanly once that sync
  happens, in whichever order the two land.

## Impact

- `src/vmss_api/visitor_return_visit/schemas.py` — `ReturningVisitorPrefill`
  gains one field.
- `src/vmss_api/visitor_return_visit/service.py` — `_to_prefill` passes
  `visitor_category_id=invitation.visitor_category_id` through.
- `src/vmss_api/visitor_return_visit/tests.py` — extend the existing
  returning-visitor prefill test(s) to assert the new field; add a case
  where the source invitation has no category set.
- `docs/features/visitor_return_visit.md` — field list update.
- No repository, migration, or API contract-shape change (additive field on
  an existing response; no new endpoint, no version bump per
  `api-conventions.md` §2).
