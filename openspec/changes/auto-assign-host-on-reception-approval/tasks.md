## 1. Backend capability (blocking — must land first)

- [ ] 1.1 Backend confirms and implements a way for the frontend to learn (or for the backend to set) the host on a reception-only (single-step) invitation when Reception approves it — see `design.md` for the two candidate shapes.

## 2. Frontend (not actionable until 1.1 lands)

- [ ] 2.1 If the backend returns host data on `approveStep`, update `InvitationActionResultSchema` (or a new response schema) and `visit-request-summary-repository.ts` to parse it.
- [ ] 2.2 If the backend sets the host server-side with no contract change, confirm the existing post-approve `getDetail` re-fetch already picks up the new `hostNameOrEmail` — likely no code change needed beyond verification.
- [ ] 2.3 Verify against a live single-step reception approval that the card and Visitor Info modal show the approver as host after approval.
