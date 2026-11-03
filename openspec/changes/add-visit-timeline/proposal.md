## Why

The invitation detail modal's "Timeline" section is stitched together from a handful of timestamp fields (submitted, approved, checked in/out…). It cannot show who did what, badge prints/reprints, ID/photo capture, or notifications. The API now exposes a read-only audit-backed visit timeline, so staff can see the full history of a visit.

## What Changes

- Add a paged, sortable, date-filterable **visit timeline** list, loaded from `GET /invitations/{invitationId}/timeline` (whole visit, incl. individual visits) or `GET /visitors/{visitorId}/timeline` (a co-visitor of a group invitation).
- Show it in the invitation detail modal's Timeline section for users holding `timeline:view` (Admin, Reception, Security); hide it otherwise. The existing timestamp-based summary stays as the fallback.
- Render each event with a label/icon per `eventType`, the display-ready `summary` (shown verbatim, never parsed), `occurredAt`, and `actorName` (omitted when `null`, i.e. system/visitor actions).
- Unknown `eventType` values render as a generic event; an empty result renders an empty state, not an error.
- Handle 403/404/422 via the standard error envelope.
- Non-goals: zone/overstay events, client-side redaction, feature flag, backfilling history.

## Capabilities

### New Capabilities
- `visit-timeline`: Fetching and displaying the audit-backed event timeline of a visit (invitation or group co-visitor), with paging, sorting, date filtering, and empty/error states.

### Modified Capabilities

## Impact

- `src/data/api/api-endpoints.ts`: two new `GET` endpoints (`hasToken: true`).
- `src/domain/entities/`: new `visit-timeline-schema.ts` (reuses `PaginationMetaSchema`).
- `src/data/repositories/`, `src/infrastructure/`, `src/data/use-cases/`: new port, adapter, use case; wiring in `src/composition-root.ts`.
- `src/presentation/components/invitation-board/VisitorInfoModal.tsx` plus a new timeline component/hook.
- Permission check uses `permissions.can('timeline:view')`; the fallback role map in `presentation/utils/permissions.ts` may need the code for API versions that omit `permissionCodes`.
- Backend reference `docs/features/timeline.md` is not in this repo; the contract in the request is the source of truth.
