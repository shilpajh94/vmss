## Context

See proposal.md - Why. Two constraints shape this design:

1. The wizard's final submission (`POST /registrations/walk-in`) sends the primary contact's ID-proof and profile-photo files inline as real file bytes in one multipart request — `useVisitorRequestWizard`'s `fileRegistry` maps a local `fileRef` string to an actual `File` object, recovered by that ref at submit time (`src/presentation/pages/visitor-request/hooks/use-visitor-request-wizard.ts`, `submit()`). There is no existing "submit by reference to an already-uploaded file" path on that endpoint.
2. The prefill's `idProofUrl`/`photoUrl` are presigned, time-limited GET URLs (`?exp=...&sig=...`) served by the backend's file storage, not endpoints the frontend otherwise talks to.

## Goals / Non-Goals

**Goals:**
- Let a returning visitor's primary-contact ID-proof and profile-photo fields default to their most recent prior file, with an explicit keep/replace choice.
- Do this without any backend/API change — the presigned URLs are already fetchable directly from the browser (confirmed: a photo URL returns 200 with `image/jpeg`).

**Non-Goals:**
- No change to the submission endpoint or its multipart contract.
- No reuse for additional group visitors or for the ID-proof type-only fields already prefilled (those are unaffected).
- No persistent storage of the fetched file beyond the current wizard session.

## Decisions

### Decision 1: Resolve "keep existing" to a real `File` by fetching the presigned URL client-side, then feed it through the unchanged `fileRegistry`/submit path
When the visitor keeps the existing file, `fetch(existingUrl)` → `Blob` → wrap in a `File` (inferring a filename/extension from the URL's content-type or path) → register it in `fileRegistry` under a `fileRef` exactly as `uploadFile()` does for a freshly picked file. `submit()` then needs no changes: it already just looks up whatever `File` sits behind `idProofFileRef`/`profileImageFileRef`.
- **Alternative considered**: have the backend accept a reference (existing file id/URL) instead of bytes on `POST /registrations/walk-in`. Rejected — needs an API change and a round trip with the API team, when the file is already directly fetchable.

### Decision 2: Fetch-and-register the existing file eagerly when the wizard mounts with a prefill URL, not lazily at submit time
Presigned URLs carry an expiry (`exp`); the wizard is a multi-step form a visitor can sit on for minutes. Fetching once when the initial data resolves (rather than right before the final submit, which could be much later) minimizes the risk of hitting an expired signature. The fetched `File` is cached in `fileRegistry` the same way a manually uploaded file would be, so once fetched it behaves identically regardless of how much later submission happens.
- **Alternative considered**: fetch lazily at submit time. Simpler, but reopens the expiry race this change exists to avoid; rejected.
- Each field independently tracks its own existing-file fetch state (`loading` / `ready` / `failed`) so one field's slow or failed fetch doesn't block the other, or the rest of the wizard.

### Decision 3: A failed existing-file fetch degrades to "must upload fresh," not a hard error
If the eager fetch fails (expired signature, network error, or — see Risks — CORS), the field falls back to the normal empty fresh-upload control rather than blocking the wizard. The visitor loses the convenience for that one field but can still complete the request.

### Decision 4: Existing-file reuse is scoped to the primary contact only
Matches how the rest of the prefill (name, email, phone, ID-proof type) already only ever populates the primary contact (`use-visitor-request-wizard.ts` comment: "only populated for a returning visitor"). Additional group visitors have no identity to look up a prior file for.

## Risks / Trade-offs

- **[Risk] The presigned URL's storage host may not send CORS headers permitting a cross-origin `fetch()` from the portal's origin.** This project has hit this exact failure mode before (audit-report download switched from `window.open` to a `fetch`-based blob download and broke on stage due to missing CORS headers on that route — see the audit-download-CORS precedent). Mitigation: verify CORS on the file-storage URLs in the target environment before relying on this approach in production; Decision 3's graceful fallback (fresh-upload control) means a CORS failure degrades the feature rather than breaking the wizard, but it should still be verified rather than discovered in production.
- **[Risk] Inferring a `File` name/type from a presigned URL is best-effort** (the URL path isn't guaranteed to carry a clean extension). Mitigation: fall back to the response's `Content-Type` header for the MIME type, and a generic name (`id-proof`, `profile-photo`) with an extension derived from that content type; the backend only needs valid file bytes and a plausible name, not a specific one.
- **[Trade-off] Eager fetch spends bandwidth/time on files the visitor might immediately replace anyway.** Accepted — files are small (confirmed prior example: ~531KB), and this is bounded to at most two fetches per wizard session for a returning visitor.

## Migration Plan

No data migration. Frontend-only change, released as a normal deploy. If the CORS risk above turns out to block fetching in an environment, the fallback (Decision 3) means the wizard continues to work exactly as it does today for every field where the fetch fails — safe to ship even if that risk isn't fully resolved beforehand, though it should be checked in the target environment first.
