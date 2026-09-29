## Context

`useInvitationsBoard` (`src/presentation/hooks/use-invitations-board.ts`) is shared by `staff-dashboard` and `admin-invitations`. Today it does one fetch on mount and exposes a manual `refresh()`; there is no polling anywhere in the codebase (no react-query/SWR, no existing `setInterval` data-fetch pattern) and no filter state beyond free-text `search`. See proposal.md for why the current UI (three refresh controls, inert Filters) needs to change.

## Goals / Non-Goals

**Goals:**
- One refresh control on the staff dashboard, still calling the existing `refresh()` path.
- Silent interval-based auto-refresh that doesn't disrupt an in-progress deny/reschedule/delegate flow.
- Purpose-of-Visit and Registration-Type filtering, composable with existing search, using the existing `DropdownFilter` UI pattern from `staff-audit-trail`.
- No change to `admin-invitations`'s current behavior (it doesn't render a Filters control, so it must default to unfiltered).

**Non-Goals:**
- No backend/query-param filtering — this stays client-side over the already-fetched `VisitRequestSummary[]`, consistent with how `search` already filters client-side.
- No change to the polling model for any other page (audit trail, admin board) — scoped to `useInvitationsBoard`.
- No status filter — status is already expressed by the four board columns.

## Decisions

**Auto-refresh via `setInterval` inside `useInvitationsBoard`, not a new fetching library.** The codebase has no query-library convention (Explore confirmed zero usage of react-query/SWR/`refetchInterval`); introducing one for a single hook would be disproportionate. A `useEffect` with `setInterval(() => void loadDashboard({ silent: true }), 30_000)` (cleared on unmount) matches the existing manual-fetch style used everywhere else in this hook.

**"Silent" refresh reuses `loadDashboard` with a flag instead of a separate function.** `loadDashboard` currently always sets `isLoading`. Adding a `silent` parameter (default `false`) that skips the `setIsLoading(true)`/`setIsLoading(false)` calls avoids duplicating the fetch/merge logic while satisfying "no full-board loading state" from the spec. Errors during a silent refresh still surface via the existing `toast.error` path but do not set `errorMessage` (which currently replaces the whole board with an error screen) — an interruption a staff member didn't ask for shouldn't hide data they're currently looking at.

**Auto-refresh pauses via a ref-tracked "action in progress" flag, not by disabling the interval's `setInterval` itself.** Simplest correct implementation: the interval always fires, but `loadDashboard`/the interval callback checks a ref that's `true` whenever `pendingDenyId`/`pendingRescheduleId`/`pendingDelegateId` is set (or `denyingId`/`reschedulingId`/`delegatingId`), and skips the fetch if so. Considered gating the whole `setInterval` on those state changes (tearing down/recreating the interval), but that resets the 30s countdown every time a dialog opens/closes, which is unnecessary complexity for no behavioral benefit — a skipped tick just means the next tick (≤30s later) retries.

**Filter state lives in `useInvitationsBoard` next to `search`, not in a separate hook.** `filteredRequests` already exists as the single place `search` is applied before the board is grouped into columns; adding `purposeFilter`/`registrationTypeFilter` state there and extending that same `useMemo` keeps one filtering pipeline instead of two. `admin-invitations` gets the new state/setters through the shared hook but simply never renders controls for them, so they stay at their default ("all") — no behavior change there.

**Purpose-of-Visit options are derived from the currently loaded requests' distinct `purposeOfVisit` values, not a hardcoded list.** There's no admin-configured enum for purpose of visit in the domain schema (it's a free-text-ish field, e.g. "business-meeting", "Interview" in the screenshot) — hardcoding known values would silently miss real ones. Deriving the option list from loaded data (plus an "All" default) matches what's actually on the board, at the cost of the option list being empty until data loads (acceptable, since the whole board is empty then too).

**Registration Type options are the fixed enum from the schema** (`individual` / `group`, from `VisitRequestSummarySchema.registrationType`), since that field is a closed `z.enum`, unlike purpose of visit.

## Risks / Trade-offs

- **Fixed 30s interval is a guess, not a stated product requirement** → flagged as an assumption in proposal.md; easy to adjust to a different constant if the user wants a different cadence.
- **Silently swallowing `errorMessage` during background refresh could mask a persistent backend outage** (staff would only see toast errors, which can be missed) → mitigated by still calling `toast.error` on every failed silent refresh, and the next manual/automatic tick will retry; if the very first (non-silent) load fails, the existing full error screen still applies since that call is not `silent`.
- **Deriving Purpose-of-Visit options from loaded data means the filter's option list can change between refreshes** (a value disappears if no visible request currently has it) → acceptable for a client-side convenience filter; matches how the board itself already changes on refresh.

## Migration Plan

No data migration. Rollout is a single frontend deploy; if auto-refresh or filtering misbehaves, revert the deploy — no persisted state or API contract changes to unwind.
