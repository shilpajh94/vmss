## Context

See proposal.md for the root-cause trace. `VisitorFieldsForm.tsx` currently has:

```ts
const visitorCategoryOptions = visitorCategories?.length
  ? visitorCategories.map((category) => ({ value: category.id, label: category.name }))
  : VISITOR_CATEGORY_OPTIONS
```

`VISITOR_CATEGORY_OPTIONS` is a hardcoded array whose `value`s (`'vendor'`, `'general-visitor'`, etc.) are display slugs, not real ids, and get sent to the API verbatim as `visitorCategoryId` via `toVisitRequest()`. The component doesn't currently distinguish "still loading" from "loaded and empty" from "failed" — `visitor-request.tsx`'s `loadVisitorCategories` catches any error and leaves `visitorCategories` as `undefined` either way, so all three states collapse into the same `visitorCategories?.length` falsy check that triggers the fallback.

## Goals / Non-Goals

**Goals:**
- Make it structurally impossible for the Visitor Category field to submit a value that isn't a real catalog id.
- Give the visitor a visible, actionable state (loading / error+retry) instead of a silently-fake dropdown when the catalog isn't available.

**Non-Goals:**
- Diagnosing why the specific reported session got an empty/failed categories fetch when the backend and data are confirmed correct — that's an environmental/observability question (e.g. inspect the network tab, check for a rate-limit trip from repeated local testing against the `60/minute` limiter on this endpoint), not a code defect this change needs to reproduce or fix.
- No change to `PrimaryContactCard.tsx` (staff wizard) — it already has no such fallback and isn't affected.

## Decisions

- **Delete the fallback outright rather than "fixing" its values**: there's no set of hardcoded ids that could ever be correct across tenants (visitor categories are tenant-configured data, per `database-architecture.md` §2's schema-per-tenant model) — any hardcoded id would be right for one tenant's seed data and wrong for every other tenant's. The only correct fix is "never fabricate options"; loading/error states are the only legitimate substitute for "no data yet."
- **Track fetch state explicitly, not just the data**: replace `visitorCategories: VisitorCategory[] | undefined` (currently ambiguous between "loading" and "failed") with a small state shape distinguishing `loading | error | loaded` in `visitor-request.tsx`, passed down to `VisitorFieldsForm.tsx` so it can render the right one of the three states from proposal.md instead of inferring it from `undefined` vs `[]`.
- **Block progression via the existing validation path**: `VisitorInfoStep.tsx`/`use-visitor-request-wizard.ts`'s existing `visitorCategory` required-field check already blocks Next when it's empty; with the fallback removed, an unavailable catalog naturally leaves `visitorCategory` unset (no fake value to select), so no new blocking logic is needed beyond the existing required-field validation plus the new error/retry UI.

## Risks / Trade-offs

- [Risk] If the categories fetch is flaky in production for reasons other than the reported case, visitors would now be fully blocked from registering (instead of completing with a category that silently fails at the very end). → Mitigation: this is the intended trade-off — a visible, immediate "can't proceed, please retry" is strictly better than an invisible failure discovered only after completing the entire multi-step wizard and submitting. The retry action gives the visitor a way to recover without reloading the whole wizard and losing their progress.
