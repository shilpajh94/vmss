## Context

Both pages are driven by `use-invitations-board` (via `useAdminInvitations` / the staff equivalent), which returns per-status `columns` (requests, total, hasMore, loadMore, resetKey) plus filters and every action handler. `ResponsiveBoard` renders the columns. The list view can sit beside it using the same hook output, so no data-layer work is needed.

## Goals / Non-Goals

**Goals:** a good-looking, scannable list with the board's filters and actions; board stays the default.
**Non-goals:** new endpoints, server-side cross-status sorting/paging, bulk actions, calendar changes.

## Decisions

- **Switch**: a `SegmentedToggle` ("Board" / "List") with icons, placed in the page title row next to Export. The value is kept with `useStoredState`, keyed per portal (`invitations-view:admin|staff`), default `board`.
- **Data**: flatten `columns` into one array of requests (each already tagged by its column status), sort by `preferredVisitDate` + `preferredVisitTime` descending, falling back to `submittedAt`. Because the board loads a page per status, "Load more" is a small control per status that still has `hasMore`, calling that column's `loadMore`; a footer line states how many of how many are loaded.
- **Components**: `InvitationViewToggle`, `InvitationListView` (table from `lg`, stacked cards below, using `responsive-table.ts`), and a shared row-actions menu built from the same permission props `KanbanColumn` already receives (`onApproveClick`, `onRescheduleClick`, …) so behaviour and permission gating cannot diverge. Status chips reuse the tone classes used in `VisitorInfoModal`.
- **Modals** stay mounted at page level; the list just calls the same request handlers.
- **Loading/empty/error**: reuse `AsyncRegion`, a `TableSkeleton`, and `EmptyState`.
- **Host column**: summaries carry no host name; use `resolvePointOfContactLabel` as the cards do.

## Risks / Trade-offs

- A flattened, loaded-so-far list is not a true server-sorted list; a status with many rows shows only its loaded pages until "Load more". Mitigated by the loaded-count footer; a real paged list endpoint is a possible follow-up.
- Duplicated action wiring between board and list; mitigated by extracting a shared action-props shape.
- Both pages are ~300 lines of near-identical props; keep the change additive rather than refactoring them.
