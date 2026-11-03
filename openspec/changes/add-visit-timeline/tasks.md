## 1. Data layer

- [x] 1.1 Add `GET_INVITATION_TIMELINE` and `GET_VISITOR_TIMELINE` to `src/data/api/api-endpoints.ts`
- [x] 1.2 Create `src/domain/entities/visit-timeline-schema.ts` (event, query, response; `eventType` as string; inferred types)
- [x] 1.3 Create `VisitTimelineRepository` port in `src/data/repositories/`
- [x] 1.4 Create the adapter in `src/infrastructure/` using `makeRequest` with `pathParams` and `queryParams`
- [x] 1.5 Create `VisitTimelineUseCase` in `src/data/use-cases/`
- [x] 1.6 Wire `apiClient → repository → use case` in `composition-root.ts` and add to `AppDependencies`

## 2. Presentation

- [x] 2.1 Add `use-visit-timeline` hook (loading, error, paging, sort order, date range)
- [x] 2.2 Add event type → label/icon map with generic fallback (icons through `assets/icons`)
- [x] 2.3 Build `VisitTimeline` component: rows, actor display, empty state, inline error + retry, load more
- [x] 2.4 Integrate into `VisitorInfoModal` Timeline section, gated by `timeline:view`; keep fallback for others
- [x] 2.5 Add `timeline:view` to the fallback role map in `presentation/utils/permissions.ts` if needed

## 3. Verification

- [x] 3.1 Unit tests for schema parsing (unknown event type, null actor) and query building
- [x] 3.2 Run `npm run lint`, `npm run build`, `npm test`
- [ ] 3.3 Manually verify: with/without permission, empty, 403/404, paging, sort toggle
