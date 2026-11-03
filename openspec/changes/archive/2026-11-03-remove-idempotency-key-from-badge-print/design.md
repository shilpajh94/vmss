## Context

See proposal.md for motivation. Today `useBadgePrinting` keeps a per-visit `Idempotency-Key` (`keysRef`), passes it through `PrintVisitorBadgeUseCase` and `CheckinRepository.printBadge`, and the infrastructure adapter sends it via `ApiClient.downloadBlob({ headers })`. The dev ingress CORS preflight does not allow that header. The same issue was already worked around for check-out by ignoring the key (`checkOut(id, _idempotencyKey)` with a TODO).

## Goals / Non-Goals

**Goals:**
- Badge print sends no custom header, so the preflight succeeds.
- No dead key-generation code left behind.

**Non-Goals:**
- Changing reprint, check-out, or `ApiClient`'s generic `headers` option (still used by nothing else for print, but kept as general capability).
- Fixing server CORS config.

## Decisions

- **Remove the parameter end to end** rather than keep an ignored `_idempotencyKey` (the check-out pattern). Leaves no misleading API; the port, use case and hook become simpler. Alternative considered: keep the signature and ignore the arg, which is a smaller diff but retains dead plumbing and `crypto.randomUUID()` calls.
- **Delete `keysRef` and its 4xx/5xx reuse logic** in the hook, since no key exists to reuse.
- **Spec delta uses ADDED** because `reception-badge-printing` is not yet in `openspec/specs/` (it lives in the unarchived `add-badge-print-flow`); if that change is archived first, this delta should be converted to MODIFIED of "Reception can print a badge".

## Risks / Trade-offs

- [Duplicate print on network-retry loses server-side dedupe] → The backend's 409 active-badge rule rejects a second print and the UI directs to Reprint; the backend states the header is optional.
- [Archive ordering with add-badge-print-flow] → Archive that change first, then adjust this delta to MODIFIED.
