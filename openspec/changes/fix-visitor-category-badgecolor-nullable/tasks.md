## 1. Fix the schema mismatch

- [x] 1.1 In `src/domain/entities/visitor-category-out-schema.ts`, add `.nullable()` to `badgeColor` on `VisitorCategoryOutSchema` (`badgeColor: z.enum(["blue", "orange", "gold", "grey"]).nullable()`).
- [x] 1.2 In `src/infrastructure/visitor-category-repository.ts`'s `toVisitorCategory()`, map `badgeColor: visitorCategoryOut.badgeColor ?? 'blue'` instead of the current direct assignment, so the domain `VisitorCategory` type's non-null contract holds.

## 2. Verification

- [x] 2.1 Confirm `curl`ing `GET /visitor-categories` and feeding the response through `VisitorCategoryListResponseSchema.parse(...)` no longer throws (can be checked via a quick node/ts-node snippet or by re-running the app against the dev tenant's seeded categories, all of which have `badgeColor: null`). (Verified with a temporary node script run against the live endpoint: all 4 seeded categories with `badgeColor: null` now parse successfully.)
- [ ] 2.2 Confirm the visitor self-service wizard's Visitor Category field now loads the real dev-tenant categories (Guest, Vendor / Contractor, Interview Candidate, Business Meeting) instead of showing "Unable to load categories."
- [ ] 2.3 Confirm the admin Visitor Categories management page (`/admin/visitor-categories`) loads its list without error.
- [ ] 2.4 Confirm the staff-created-invitation wizard's visitor category picker also loads real categories.
- [x] 2.5 Run `npm run lint` and `npx tsc -b`. (Both clean.)
