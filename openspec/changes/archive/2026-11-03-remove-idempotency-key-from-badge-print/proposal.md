## Why

On dev, `POST /api/v1/checkin/{visit_id}/badge` fails in the browser with "Request header field idempotency-key is not allowed by Access-Control-Allow-Headers in preflight response", so reception cannot print badges. The backend confirms `Idempotency-Key` is optional on this endpoint and not needed for badge print. Not sending the custom header removes it from the preflight, so the request goes through.

## What Changes

- Stop sending the `Idempotency-Key` header on the badge-print request (`POST /checkin/{id}/badge`).
- Remove the per-attempt idempotency key plumbing for badge print: key generation/retention in the badge-printing hook, the `idempotencyKey` argument on the print use case and the repository port/adapter.
- Reprint (`GET /checkin/{id}/badge?reason=`) is unchanged; it never sent the header.
- Check-out and `ApiClient` custom-header support are unchanged.

## Capabilities

### New Capabilities

### Modified Capabilities
- `reception-badge-printing`: the print requirement no longer sends an `Idempotency-Key` header or reuses a key across retries. Currently defined in the unarchived `add-badge-print-flow` change.

## Impact

- `src/infrastructure/checkin-repository.ts` (`printBadge`)
- `src/data/repositories/checkin-repository.ts` (port signature)
- `src/data/use-cases/print-visitor-badge.ts`
- `src/presentation/pages/reception-badge-printing/hooks/use-badge-printing.ts`
- Behavioral trade-off: without a key, a retried print after a network failure is no longer deduplicated by the server (see design.md).
- Backend/DevOps ingress CORS config is out of scope here.
