## Context

Reads only; follows `.claude/rules/data-api-layer.md` and clean-architecture layering. The modal at `presentation/components/invitation-board/VisitorInfoModal.tsx` already has a "Timeline" section built from detail timestamps. Endpoints use `:param` placeholders with `pathParams` (see `GET_INVITATION_DETAIL`). Paged responses reuse `PaginationMetaSchema`.

## Goals / Non-Goals

**Goals:** show the real audit-backed timeline in the existing modal, resilient to new event types and incomplete history.
**Non-Goals:** zone/overstay events, redaction, feature flag, standalone timeline page, backfill.

## Decisions

- **Endpoints**: add `GET_INVITATION_TIMELINE` (`/invitations/:invitationId/timeline`) and `GET_VISITOR_TIMELINE` (`/visitors/:visitorId/timeline`), both `hasToken: true`.
- **Schema** `visit-timeline-schema.ts`: `eventType` is `z.string()` (not an enum) so unknown values parse; export a `KNOWN_TIMELINE_EVENT_TYPES` const for label/icon lookup with a generic fallback. `occurredAt: z.string()`, `summary: z.string()`, `actorName: z.string().nullable()`. Envelope: `success`, `message`, `data[]`, `pagination: PaginationMetaSchema`.
- **Port/adapter/use case**: `VisitTimelineRepository` with `listForInvitation(id, query)` and `listForVisitor(id, query)`; query maps to `queryParams` via `ApiClient`'s `URLSearchParams` builder, dropping undefined values. One `VisitTimelineUseCase`, exposed on `AppDependencies` via lazy resolvers.
- **UI**: a `VisitTimeline` component plus `use-visit-timeline` hook (`useAppDependencies()`, `useCallback`) rendered inside the modal's Timeline section, gated by `permissions.can('timeline:view')`. Default newest-first, 20 per page, "Load more" appends pages; sort order toggle and optional date range reset to page 1.
- **Fallback**: when the user lacks permission, keep the current timestamp grid unchanged. With permission, show the real timeline above/instead of it (keep the timestamp-driven callouts such as the auto-checkout note).
- **Errors**: `ApiError` messages shown inline with retry; empty `data` shows an empty state.

## Risks / Trade-offs

- `timeline:view` may be absent from `permissionCodes` on older API deployments → add it to the fallback role map for Admin/Reception/Security (verify against backend catalog).
- The modal may not currently know the visitor id for co-visitors; start with the invitation endpoint and use the visitor endpoint only where a co-visitor view exists. Open question: does the UI offer a per-co-visitor view today?
- `docs/features/timeline.md` isn't in this repo, so behavior is based on the pasted contract.
