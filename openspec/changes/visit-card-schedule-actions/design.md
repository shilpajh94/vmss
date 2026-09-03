## Context

`VisitRequestCard` currently renders its Reschedule and Delegate forms inline, gated on `isExpanded` (see `src/presentation/components/invitation-board/VisitRequestCard.tsx`). The same pattern (state on `useInvitationsBoard`, a dedicated modal component, a shared `Modal` primitive) already exists for Deny: `pendingDenyId` / `requestDeny` / `cancelDeny` / `confirmDeny` in `src/presentation/hooks/use-invitations-board.ts` drive `DenyInvitationModal.tsx`, which wraps the shared `src/presentation/components/ui/Modal.tsx`. This change brings Reschedule and Delegate onto that same shape instead of introducing a new one. See proposal.md for motivation.

The visit-request summary payload (`VisitRequestSummarySchema`) has no `preferredVisitDate` / `preferredVisitTime` fields today; the detail payload (`invitation-detail-schema.ts`) and the create/staff-create request schemas already carry these field names, so the summary schema is extended to match rather than inventing new names.

## Goals / Non-Goals

**Goals:**
- Move Reschedule and Delegate from expand-gated inline panels to card-level buttons + modals, following the existing Deny modal pattern.
- Decouple card expansion (approval-step progress) from these two actions entirely.
- Show each card's scheduled visit date/time.

**Non-Goals:**
- Changing the Deny flow itself (already button/modal-driven via drag-to-deny; unaffected).
- Adding host name to the card (mandated by an existing, separate requirement not part of this change's scope).
- Backend changes — this assumes `LIST_VISIT_REQUESTS` already returns `preferredVisitDate`/`preferredVisitTime` on each item, per the schema-first flow the data-api-layer rule expects. If it doesn't, `parserSchema.parse` will throw a `ZodError` on load, surfacing as the existing "list failed to load" error path — see Risks.

## Decisions

- **Modal state lives in `useInvitationsBoard`, mirroring Deny.** Add `pendingRescheduleId` / `requestReschedule` / `cancelReschedule` (paired with the existing `reschedule` action, now also closing the modal on success) and `pendingDelegateId` / `requestDelegate` / `cancelDelegate` (paired with the existing `delegate` action). Alternative considered: local `useState` inside `VisitRequestCard` — rejected because the delegate modal needs `hostEmployees`/`roleNameById` already loaded on the hook, and keeping all three action dialogs (deny, reschedule, delegate) on the same hook keeps the board component's wiring uniform.
- **New sibling modal components, not a generic one.** Add `RescheduleInvitationModal.tsx` and `DelegateInvitationModal.tsx` next to `DenyInvitationModal.tsx`, each wrapping the shared `Modal`. Alternative considered: one generic "card action modal" — rejected, the three forms (reason textarea, date+time pair, role-scoped host select) don't share enough structure to justify a generic abstraction, matching the existing one-component-per-action pattern.
- **Buttons render unconditionally on the card footer** (not inside the expand branch), gated only by the same eligibility checks used today (`RESCHEDULABLE_STATUSES.has(request.status)` for Reschedule, `Boolean(detail?.currentApprovalStep)` for Delegate). Delegate's eligibility still depends on `detail`, which is preloaded for `requested`-column cards and fetched on first expand for others — unchanged from today's behavior, so the button can appear before detail resolves as absent and then appear once the detail loads, exactly as the inline panel does today.
- **Scheduled time schema field:** add `preferredVisitDate: z.string().min(1)` and `preferredVisitTime: z.string().min(1)` to `VisitRequestSummarySchema`, matching the field names already used in `staff-visit-request-schema.ts` / `visit-request-schema.ts`. Card renders them alongside the existing submitted-at row, not replacing it.

## Risks / Trade-offs

- [`LIST_VISIT_REQUESTS` doesn't actually return the two new fields yet] → Schema validation fails closed (`ZodError` on parse), which surfaces through the board's existing load-failure path (error message + retry + error notification) rather than a silent blank field. If this happens, the fields should be temporarily marked `.nullable()` until the backend ships them, or the backend is confirmed before this change is applied.
- [Splitting one card interaction into three separate modals adds a bit of click overhead vs. inline forms] → Matches the Deny action's existing UX, which staff are already used to, and keeps the collapsed/expanded card free of action forms.

## Migration Plan

No data migration. Deploy is a single frontend release: schema + card + hook changes ship together. Rollback is a plain revert (no backend or stored-state coupling).
