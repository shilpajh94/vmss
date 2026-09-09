## Context

See `proposal.md` for motivation. Confirmed by reading the current code and
specs before drafting this design:

- Both wizards (`visitor-request`, `staff-visitor-registration`) share the
  same `VisitInfoStep.tsx` component and near-identical validation hooks
  requiring `hostNameOrEmail`/`hostId` and `department`.
- `department`'s options come from a `departments` prop passed into
  `VisitInfoStep.tsx` (populated from a one-time catalog fetch at wizard
  load, filtered by the selected branch) — unlike host, there's no
  dedicated search-as-you-type integration to also remove; the catalog
  fetch itself stays, since the new Edit Invitation modal's own department
  picker (§D2) still needs it.
- The invitation board (`use-invitations-board.ts`, shared by
  `staff-dashboard` and `admin-invitations`) already has an
  action-in-progress-tracking pattern (`reschedule`, `delegate`, `approve`,
  `deny`) that a new `edit` action extends directly — same modal-trigger,
  same success/error notification convention, same board-refresh-on-success
  behavior.
- `DelegateInvitationModal` already filters its host list to holders of the
  step's `approverRoleId`, sourced from `HostEmployee.branchRoles`
  client-side. The unfiltered-for-ownership-step behavior is a small,
  targeted change to that one filter, not a new component.
- `CurrentApprovalStepSchema` already models both `approverRoleId` and
  `approverUserId` plus `delegatedToUserId` — no schema shape change needed
  to distinguish "pending on a role" vs. "pending on a person," only new
  UI states for the already-modeled null/non-null combinations.
- No logo asset exists anywhere in the repo (`src/assets`, `public`) — this
  is new asset creation, not a swap.

## Goals / Non-Goals

**Goals:**
- Remove host and department selection from both wizards with the smallest
  possible diff, given they already share the offending component/
  validation.
- Extend the existing board-action pattern (not invent a new one) for Edit.
- Make the minimal, targeted change to `DelegateInvitationModal`'s existing
  filter, not rebuild the delegation UI.
- Land a real, usable logo asset in the app shell.

**Non-Goals:**
- A UI for tenants to configure which role owns invitations by default —
  this is a backend/config concern (see companion API change's design D1);
  the web app just renders whatever role/host state the API returns.
- Persisted, cross-device notification history — the notification-center's
  existing session-only, 50-item-cap design (per its own code comments) is
  unchanged by this work; only the addressing label on each item changes.
- A tenant-facing brand/logo upload feature — the logo shipped by this
  change is a fixed static asset, not configurable per tenant.

## Decisions

### D1: Host and department removal are both subtractions from the shared `VisitInfoStep`, not a fork
Since `visitor-request` and `staff-visitor-registration` already share one
component and one validation shape, removing the host field/validation once
in `VisitInfoStep.tsx` and its shared `types.ts` covers both wizards. The
staff-assisted wizard's separate `listHostEmployeesUseCase`/
`handleSearchHosts` wiring (used only for the host picker, not for anything
else on that step) is deleted as dead code alongside the field itself; the
public wizard's `/hosts/search` (`SEARCH_HOSTS`) integration is deleted the
same way. `HostEmployee`/`listHostEmployeesUseCase` themselves are kept,
since the Delegate modal still needs a host-employee list to populate its
picker.

Department follows the identical subtraction — same component, same shared
validation hook, same "remove once, both wizards benefit" shape — but with a
smaller footprint: there's no per-field network integration to also delete
(unlike host's `/hosts/search`), since `department` options come from a
`departments` prop populated by a catalog fetch the page-level wizard
component already makes once at load. That fetch, and the `departments`
prop itself, are kept — only the Visit Info step's field and its
required-field check are removed — because the new Edit Invitation modal
(§D2) reuses the same catalog for its own department picker.
- **Alternative considered**: keep `/hosts/search` wired but unused, in case
  a future feature wants it. Rejected — dead network calls and unused
  props are exactly what `project-rules.md`-equivalent hygiene (no
  speculative code) argues against; it can be re-added if a real future
  need appears.

### D2: Edit Invitation is a new modal following the Reschedule/Delegate pattern exactly, not a new page
`RescheduleInvitationModal`/`DelegateInvitationModal` (from the recently
landed `visit-card-schedule-actions` change) establish the pattern: a
card-footer button, gated by `canX` eligibility logic in
`VisitRequestCard.tsx`, opening a modal, wired through
`use-invitations-board.ts`'s action-in-progress tracking. `EditInvitationModal`
follows the identical shape — same success/error notification convention,
same board-refresh-on-success. The read-only visitor-personal-fields/host
section in that modal is rendered from the same `InvitationDetail` data the
expanded-card view already fetches; no new API call is introduced solely for
display.
- **Alternative considered**: a dedicated "Edit Invitation" page/route
  instead of a modal. Rejected — inconsistent with every other invitation
  action in this codebase, all of which are modals triggered from the board;
  a page would also lose the board-context (search/filter state) the
  staff member was in.

### D3: The Delegate host-picker filter change is scoped by step position (stepOrder 0), matching the API's own scoping
`DelegateInvitationModal`'s filter currently keys off
`currentApprovalStep.approverRoleId` alone. The fix adds a check for
`currentApprovalStep.stepOrder === 0` (or an equivalent "is this the
ownership step" flag the API detail response should expose — confirm exact
field name against the companion API change's `InvitationDetailOut` shape
before implementation) to skip the role filter only for that specific step,
mirroring exactly how the API's own delegate-eligibility exception is scoped
by step position, not by which role the step happens to name (see companion
API change's design D3). Keeping the two scoped the same way avoids a
confusing mismatch where the UI would let someone pick a delegate the API
then rejects, or vice versa.

## Risks / Trade-offs

- **[Risk]** This change ships web-side host-field removal ahead of, or
  behind, the API's removal of `hostId`/`hostNameOrEmail` from its create
  schema. → **Mitigation**: the API accepts-but-ignores those fields rather
  than rejecting them (see companion change's design), so the web app can
  stop sending them slightly before or after the API stops honoring them
  without either side breaking; no strict ordering is required, but
  deploying them together avoids a window where staff see a host field that
  silently does nothing.
- **[Risk]** Removing the role-filter from `DelegateInvitationModal` for
  `stepOrder` 0 means the host picker for that step could show a very long,
  unfiltered list of every active host employee at the branch for a large
  tenant. → **Mitigation**: out of scope to add search/filter-as-you-type
  to that picker in this change if it doesn't already have it — flag as a
  follow-up if a design review surfaces this as a real usability problem
  once branch sizes are known; the existing picker component's own
  search/filter behavior (if any) is inherited as-is.
- **[Trade-off]** Logo asset is produced as a static SVG shipped in this
  change rather than sourced from a design tool/brand-kit process, since no
  such process exists yet for this project. Accepted as a reasonable
  placeholder the organization can swap later without any code structure
  change (single asset file reference).

## Open Questions

- Exact field name (or derived boolean) the API's `InvitationDetailOut`
  exposes to let the web app detect "this is the ownership step" for D3's
  filter-skip logic (`stepOrder === 0` client-side check vs. a dedicated
  flag the API adds) — confirm against the companion API change's actual
  schema once its implementation lands; does not change this change's
  approach or task breakdown, only one field reference within it.
