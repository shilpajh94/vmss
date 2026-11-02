## 1. Data layer

- [x] 1.1 Add endpoints to `API_ENDPOINTS`: tenant read, tenant settings PATCH, checkin search, verify-id, print badge, reprint badge, scan check-out, scan re-enter (scan routes `hasToken: false`)
- [x] 1.2 Add optional extra headers (e.g. `Idempotency-Key`) to the existing `ApiClient.downloadBlob`; parse JSON error envelopes into the existing error type
- [x] 1.3 Add Zod schemas: tenant (`badgePrintFlowEnabled`), checkin search row/page, scan result `{id, trackingId, status, checkInStatus}`
- [x] 1.4 Add ports, adapters, and use cases (tenant settings, checkin search/verify/print/reprint, badge scan)
- [x] 1.5 Wire in `composition-root.ts` and `AppDependencies`

## 2. Gating

- [x] 2.1 Hook combining `badgePrintFlowEnabled` and `visitors:print_badge`; hide nav and guard route
- [x] 2.2 Map any `/checkin/*` 404 to a feature-off state

## 3. Reception screen

- [x] 3.1 Page with search, paging, row indicators, empty state
- [x] 3.2 ID verified action
- [x] 3.3 Print action with per-attempt idempotency key; PDF open/print with popup fallback; revoke object URL
- [x] 3.4 409 message mapping
- [x] 3.5 Reprint confirm dialog with required 1-255 char reason; ensure no auto/prefetch path

## 4. Scan page

- [x] 4.1 Public route with token input and `?token=` prefill (no auto-submit)
- [x] 4.2 Check-out and Re-enter buttons with success, 400, 429, 404 handling

## 5. Admin setting

- [x] 5.1 Toggle gated by `tenants:update`, PATCH, revert on failure

## 6. Verify

- [x] 6.1 Run `tsc`, lint, build, unit tests for 409/idempotency/reason validation
- [ ] 6.2 Manually verify with flag off (nothing visible, 404 neutral) and on (full flow)

## 7. Photo upload

- [x] 7.1 Backend: `POST /checkin/{visit_id}/photo` (never replaces an existing photo; tests written, not run locally)
- [x] 7.2 Frontend: endpoint, port, adapter, use case, `uploadFile` path params, "Upload photo" action on rows without a photo
