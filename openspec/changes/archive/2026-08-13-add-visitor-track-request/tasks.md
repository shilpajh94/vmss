## 1. Domain schema

- [x] 1.1 Create `src/domain/entities/tracking-lookup-response-schema.ts` (`TrackingLookupResponseSchema`: trackingId, statusLabel, statusTone, requestedDate, assignedHost, totalVisitors, timelineStage)

## 2. API contract

- [x] 2.1 Add `TRACK_VISIT_REQUEST` (`GET /visit-requests/track`, `hasToken: false`) to `src/data/api/api-endpoints.ts`

## 3. Repository, use case, composition root

- [x] 3.1 Create `src/data/repositories/visit-tracking-repository.ts` (port: `lookup(trackingId): Promise<TrackingLookupResponse>`)
- [x] 3.2 Create `src/infrastructure/visit-tracking-repository.ts` (adapter implementing the port via `ApiClient.makeRequest` with `queryParams: { trackingId }`)
- [x] 3.3 Create `src/data/use-cases/track-visit-request.ts`
- [x] 3.4 Wire `resolveVisitTrackingRepository` → `TrackVisitRequestUseCase` in `composition-root.ts`; expose it on `AppDependencies`

## 4. Page components

- [x] 4.1 Create `src/presentation/pages/visitor-track/Components/TrackingLookupCard.tsx` (search icon, heading, description, tracking-ID input, "Track Request" button, inert "Track via Email" link)
- [x] 4.2 Create `src/presentation/pages/visitor-track/Components/StatusPanel.tsx` (tracking ID, status badge colored by `statusTone`, requested date / assigned host / total visitors, 4-stage timeline driven by `timelineStage`)

## 5. Page, hook, and route wiring

- [x] 5.1 Create `src/presentation/pages/visitor-track/hooks/use-visitor-track-lookup.ts` (tracking-ID input state, lookup status idle/loading/success/error, calls the use case via `useAppDependencies()`)
- [x] 5.2 Create `src/presentation/pages/visitor-track/visitor-track.tsx` composing the shared `PortalHeader` (`backTo="/"`), hero title bar, `TrackingLookupCard`, conditional `StatusPanel`/error state, and shared `PortalFooter`
- [x] 5.3 Register `/visitor/track` in `src/App.tsx`

## 6. Verification

- [x] 6.1 Run the app locally and confirm submitting the lookup form with an empty tracking ID is blocked with a validation message
- [x] 6.2 Confirm submitting a tracking ID attempts the lookup and, against the (absent) backend, shows the error state without crashing
- [x] 6.3 Confirm the "Track via Email" link is visible and does not trigger any lookup
- [x] 6.4 Confirm the landing page's "Track Request" button now lands on a working page, and the back chevron returns to `/`
- [x] 6.5 (extra) Verified the success state with a mocked response — status badge, requested date/host/visitor count, and 4-stage timeline all render correctly against the Figma design
