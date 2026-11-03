## 1. Backend contract

- [x] 1.1 Agree with backend the JSON for print/reprint (token, name, purpose, host, photo) and confirm the photo access method
- [x] 1.2 Add `BadgeCardSchema` and inferred type in `src/domain/entities/checkin-schema.ts`

## 2. Data layer

- [x] 2.1 Change the print/reprint port methods in `src/data/repositories/checkin-repository.ts` to return the badge type
- [x] 2.2 Update the infrastructure adapter to use `makeRequest` with `BadgeCardSchema` and update `print-visitor-badge.ts` / `reprint-visitor-badge.ts`

## 3. Badge card UI

- [x] 3.1 Add the QR library dependency
- [x] 3.2 Build `BadgeCard` under `reception-badge-printing/Components/` (header, photo, Name/Purpose/Meet To rows, QR, dash placeholders)
- [x] 3.3 Add print-only styles (`@page` ID-card size, hide page chrome) using theme tokens

## 4. Print flow

- [x] 4.1 Update `use-badge-printing.ts` to hold badge data, call `window.print()` and clear the token on `afterprint`
- [x] 4.2 Remove the PDF `openPdf`/`pdfLink` path and its fallback UI; keep existing 409 error messages and reprint reason dialog

## 5. Verification

- [ ] 5.1 Scan the printed QR on the badge scan page for check-out and re-entry; confirm reprint invalidates the old QR
- [ ] 5.2 Manually check print output in Chrome and Firefox; run lint and typecheck
