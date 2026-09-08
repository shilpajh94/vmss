## Why

A real submission of the visitor self-service wizard (`POST /api/v1/registrations/walk-in`) failed with:

```
1 validation error for InvitationCreate
visitorCategoryId
  Input should be a valid UUID, invalid character: found `v` at 1 [type=uuid_parsing, input_value='vendor', input_type=str]
```

Tracing this: `VisitorFieldsForm.tsx` (`src/presentation/pages/visitor-request/Components/steps/VisitorFieldsForm.tsx`) defines a hardcoded `VISITOR_CATEGORY_OPTIONS` array — `{ value: 'vendor', label: 'Vendor' }` and similar — used as the Visitor Category dropdown's options whenever the real, API-loaded `visitorCategories` list is empty or hasn't loaded (`visitorCategories?.length ? visitorCategories.map(...) : VISITOR_CATEGORY_OPTIONS`). The comment on this fallback claims it's needed because "no staff session token [is] available for an anonymous public visitor," but that reasoning doesn't hold: `GET /visitor-categories` (VMSS_API, `visitors/router.py::list_visitor_categories`) is explicitly public — it uses `public_tenant_db`, which resolves the tenant from `settings.default_tenant_slug` when no bearer token is presented, specifically so "the pre-registration form needs to render a category picker before a visitor authenticates" (its own docstring). Querying the dev database confirms the default tenant has real, seeded visitor categories with real UUIDs (e.g. `11b23f35-31ed-4927-924b-659e5f373b11` for "Vendor / Contractor"). So whatever caused `visitorCategories` to come back empty in the reported session (a transient fetch failure, or some other issue), the response was — correctly — either an error or an empty list, and the wizard silently substituted fake, non-UUID placeholder values that look like real options but can never be accepted by the API. A visitor who picks "Vendor" from this fallback list has no way to know their selection is fake, and only finds out after completing every other step and submitting.

The staff-created-invitation wizard's equivalent picker (`PrimaryContactCard.tsx`) has no such fallback — it maps `(visitorCategories ?? []).map(...)`, which just renders zero options when the list is empty, so this defect is isolated to the visitor self-service wizard.

## What Changes

- Remove the hardcoded `VISITOR_CATEGORY_OPTIONS` fallback from `VisitorFieldsForm.tsx` entirely — a Visitor Category dropdown must only ever offer options backed by real ids from the loaded catalog.
- When the visitor-category catalog hasn't loaded yet or came back empty, the Visitor Category field shows a loading or "unavailable" state instead of a populated-looking dropdown, and the Visitor Info step cannot be completed until a real category is selected (consistent with the field already being otherwise required).
- Surface a distinguishable error state (instead of the current silent `catch {}` in `visitor-request.tsx`'s `loadVisitorCategories`) so a visitor whose categories genuinely fail to load sees a message and a way to retry, rather than a wizard that quietly offers fake choices.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `visitor-request-wizard`: "The primary contact's visitor category is submitted as the invitation's category" is extended to require that the submitted id always originates from the live-loaded catalog, never a placeholder. A new requirement covers the loading/unavailable/retry states for the Visitor Category field.

## Impact

- Affected code: `src/presentation/pages/visitor-request/Components/steps/VisitorFieldsForm.tsx` (remove the fallback options, add a loading/unavailable state), `src/presentation/pages/visitor-request/visitor-request.tsx` (`loadVisitorCategories`'s silent `catch`), and `use-visitor-request-wizard.ts`/`VisitorInfoStep.tsx` if the step's own validation needs to account for a categories-unavailable state.
- No backend change — `GET /visitor-categories` and `POST /registrations/walk-in` already behave correctly; this is purely a frontend correctness fix.
- Separately worth checking (not part of this change's code fix, since it's environmental rather than a code defect): why the categories fetch returned empty in the reported browser session, given the endpoint and data are confirmed to work — e.g. checking the browser network tab for the actual `GET /visitor-categories` response at the time of the report.
