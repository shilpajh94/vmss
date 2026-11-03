## Why

The visitor badge is a backend-rendered PDF that the frontend only opens in a new tab, so reception cannot change its look. We want an ID-card-style badge: a coloured header reading "VISITOR ID CARD", a visitor photo, labelled rows (Name, Purpose, Meet To) and a scannable **QR code** at the bottom where a barcode sits on the reference design. The QR must be the same signed token the scan page already accepts for check-out and re-entry.

## What Changes

- Add a frontend-rendered visitor badge card (HTML/CSS, Tailwind, printable at badge size) showing the header, photo, Name / Purpose / Meet To rows, and a QR code encoding the signed badge token.
- Print the card from the browser (`window.print()` with a print-only stylesheet) instead of opening the backend PDF.
- Add a QR rendering dependency (client-side, no network) and render the QR from the badge token.
- Extend the print and reprint flows to obtain the badge data (token, photo, purpose, host) as JSON rather than only a PDF blob.
- Keep the print rules unchanged: ID verified, photo present, visit approved, reprint only behind the reason dialog and never auto-called.
- **BREAKING (design decision)**: reverses `add-badge-print-flow`'s "the PDF is the badge" non-goal.
- **Backend dependency**: the frontend currently never receives the signed QR token or the purpose/host fields; the backend must expose them (see design.md). This change cannot ship until it does.

## Capabilities

### New Capabilities
- `visitor-badge-card`: layout, content, QR encoding and print behaviour of the on-screen/printed visitor badge.

### Modified Capabilities
<!-- None: openspec/specs has no reception-badge-printing spec yet; its behaviour lives in the unarchived add-badge-print-flow change. -->

## Impact

- `src/presentation/pages/reception-badge-printing/`: new badge card component, print styles, hook changes in `use-badge-printing.ts` (replace `openPdf`).
- `src/data/use-cases/print-visitor-badge.ts`, `reprint-visitor-badge.ts`, `src/data/repositories/checkin-repository.ts`, matching infrastructure adapter and `API_ENDPOINTS` entries: return validated JSON instead of a `Blob`.
- `src/domain/entities/checkin-schema.ts`: new Zod badge schema (token, photo, name, purpose, host).
- `package.json`: one QR-rendering library.
- Backend: JSON badge payload (or equivalent) on print/reprint; photo retrieval for rendering.
