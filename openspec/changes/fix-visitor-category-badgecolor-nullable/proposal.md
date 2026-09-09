## Why

While verifying `fix-visitor-category-invalid-id-fallback`'s new "Unable to load categories" error state in a real browser, the visitor self-service wizard showed that error state even though the backend was fully healthy. Tracing it down: the backend's `GET /visitor-categories` (VMSS_API `VisitorCategoryOut.badge_color`) is `str | None` — a category can legitimately have no badge color, and every category currently seeded in the dev tenant does (`badgeColor: null` in the raw response, confirmed via `curl` against the backend directly, through the vite dev-server proxy, and at the exact URL the browser hits — all three return `200` with valid data). The frontend's `VisitorCategoryOutSchema` (`src/domain/entities/visitor-category-out-schema.ts`) declares `badgeColor: z.enum(["blue", "orange", "gold", "grey"])` with **no** `.nullable()`. `ApiClient.makeRequest` calls `parserSchema.parse(await response.json())`, so every category in the response fails Zod validation and the whole list request throws — the fetch succeeds at the network level but is rejected during client-side parsing.

This is a pre-existing defect, not something introduced by the fallback fix — it's exactly the "why did the real fetch come back empty" question that change's proposal flagged as a separate, unconfirmed item, now confirmed. It's more consequential than just the visitor-request wizard: `HttpVisitorCategoryRepository.list()` is the single shared implementation behind `listVisitorCategoriesUseCase`, used by the visitor self-service wizard, the staff-created-invitation wizard (`staff-visitor-registration.tsx`), the admin workflow-rules form (`admin-workflows`), and the admin Visitor Categories management page itself (`admin-visitor-categories`) — every one of these currently fails to load real category data whenever any category has no badge color set, which is true for all four categories seeded in this dev tenant right now.

## What Changes

- Make `badgeColor` nullable in `VisitorCategoryOutSchema` (`src/domain/entities/visitor-category-out-schema.ts`), matching the backend's actual `str | None` contract.
- Update `toVisitorCategory()` (`src/infrastructure/visitor-category-repository.ts`) to map a `null` wire value to the domain `VisitorCategory` type's existing default (`"blue"`, per `VisitorCategorySchema`'s own `.default("blue")` and the admin spec's "badge color defaults to the first palette option"), so every other consumer of the domain type keeps its existing non-null assumption intact — the fix is isolated to the wire-parsing boundary.
- No behavior is being newly specified — the admin, staff, and visitor-facing category pickers were always supposed to load and display real categories; this restores that already-expected behavior. Per project convention, this change sets `skip_specs: true` rather than inventing a requirement delta for a straightforward defect fix.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — `skip_specs: true` (see above; no spec-level behavior is changing, only a client-side parsing defect is being fixed).

## Impact

- Affected code: `src/domain/entities/visitor-category-out-schema.ts`, `src/infrastructure/visitor-category-repository.ts`.
- Fixes every consumer of `listVisitorCategoriesUseCase`/`HttpVisitorCategoryRepository.list()`: the visitor self-service wizard, the staff-created-invitation wizard, the admin workflow-rules form, and the admin Visitor Categories management page.
- No backend change — the backend's contract (`badge_color: str | None`) was already correct; only the frontend's Zod schema was too strict.
