## 1. Track fetch state explicitly

- [x] 1.1 In `visitor-request.tsx`, replace the `visitorCategories: VisitorCategory[] | undefined` state with an explicit status, e.g. `{ status: 'loading' | 'error' | 'loaded', categories: VisitorCategory[] }`, and update `loadVisitorCategories` to set `'error'` on failure instead of silently doing nothing.
- [x] 1.2 Add a `retryLoadVisitorCategories` (or reuse `loadVisitorCategories`) callback that can be triggered from the UI to re-attempt the fetch, resetting status to `'loading'` first.
- [x] 1.3 Pass the new status/categories shape down through `VisitorInfoStep.tsx` to `VisitorFieldsForm.tsx` in place of the current plain `visitorCategories?: VisitorCategory[]` prop, and to `ReviewConfirmStep.tsx` (adjust its usage to read `.categories` instead of a bare array — it only needs the loaded list for display).

## 2. Remove the broken fallback and add loading/error UI

- [x] 2.1 In `VisitorFieldsForm.tsx`, delete the `VISITOR_CATEGORY_OPTIONS` constant and its use in `visitorCategoryOptions` entirely.
- [x] 2.2 Render the Visitor Category `SelectField` with `disabled` and a "Loading categories…" placeholder when status is `'loading'`.
- [x] 2.3 Render an error state when status is `'error'` (or `'loaded'` with zero categories): a message near the field plus a retry button wired to `retryLoadVisitorCategories`, and keep the field disabled/empty so nothing fake can be selected.
- [x] 2.4 When status is `'loaded'` with at least one category, render the `SelectField` exactly as it works today, options built only from the real catalog.

## 3. Verification

- [x] 3.1 Confirm (via code review or a temporary throw in `loadVisitorCategories`) that when the fetch fails, the Visitor Category field shows the error/retry state and Next remains blocked (existing required-field validation already covers this once no fake option exists to select). (Confirmed via code review: catch sets `status: 'error'`, `isCategoryUnavailable` becomes true, `SelectField` is disabled with an empty options list, `value.visitorCategory` can never be populated, and `validateVisitorContact`'s existing `!contact.visitorCategory` check keeps blocking Next.)
- [ ] 3.2 Confirm a successful fetch with the seeded dev-tenant categories (Guest, Vendor / Contractor, Interview Candidate, Business Meeting) populates the dropdown with their real ids, and that submitting with one selected sends that real UUID as `visitorCategoryId`.
- [ ] 3.3 Confirm the retry button re-attempts the fetch and recovers into the normal populated state without requiring a full page reload.
- [x] 3.4 Run `npm run lint` and `npx tsc -b`. (Both clean.)
