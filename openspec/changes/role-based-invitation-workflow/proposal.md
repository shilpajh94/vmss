## Why

The visitor self-service wizard and the staff-assisted registration wizard
both force whoever is filling the form to pick a named host up front, which
the visitor rarely knows and staff often get wrong for same-day slots. Once
submitted, the only thing anyone can change is the date/time (via Reschedule)
— if reception needs to fix the host, duration, department, or purpose, there
is no UI for it today. The notification bell also has no way to show "this
came to your role" versus "this was delegated to you personally," which will
matter once invitations start life owned by a role instead of a person.

Companion change: `VMSS_API` change `role-based-invitation-workflow` defines
the backend contract this UI work implements against — host is no longer
accepted at creation, a new edit endpoint exists, and push payloads carry new
addressing metadata.

## What Changes

- **BREAKING**: The "Host Name or Email" field is removed from the Visit Info
  step in **both** the visitor self-service wizard and the staff-assisted
  registration wizard — neither channel collects a host at creation anymore.
  `hostNameOrEmail`/`hostId` are dropped from both wizards' form state,
  validation, and submit payload; the corresponding required-field validation
  message is removed.
- The `AutocompleteField`/`onSearchHosts` wiring in `VisitInfoStep.tsx` and
  the `/hosts/search` (`SEARCH_HOSTS`) integration in the public wizard are
  removed from the creation flow. `HostEmployee`/`listHostEmployeesUseCase`
  (used by staff registration today for host lookup) stay, since they're
  still needed for the delegation picker below.
- **BREAKING**: The "Department to Visit" field is likewise removed from the
  Visit Info step in **both** wizards, for the same reason as host — a
  visitor rarely knows which internal department their contact sits under,
  and staff booking on their behalf often guess wrong for a same-day slot.
  `department` is dropped from both wizards' required-field validation and
  submit payload; the field is no longer shown at all. Reception fills it in
  afterward — once they know the visitor's actual requirements — via the new
  Edit Invitation modal below, which already covers this field. The
  underlying department catalog fetch (`departments` prop, used to populate
  the dropdown) is unaffected — it's still needed by the Edit modal's own
  department picker, so only the Visit Info step's field and validation are
  removed, not the data source.
- **New: Edit Invitation** action on the shared invitation board
  (`staff-dashboard`, surfaced identically in `admin-invitations`) alongside
  the existing Reschedule/Delegate/Approve/Deny actions. Opens a modal
  covering every visit-detail field the new `PATCH /invitations/{id}/edit`
  endpoint accepts — date/time, duration, location/building/department,
  purpose, notes — with the visitor's own personal fields (name, email,
  phone, ID proof, photo), visitor category, and host shown read-only (host
  reassignment stays exclusively the Delegate action's job, not this modal's
  — one place to change who the host is). Available while status is
  `submitted` or `approved`, matching the endpoint's eligibility.
- **Delegate modal behavior change**: `DelegateInvitationModal` currently
  filters the host-employee list down to those holding the step's approver
  role. For the invitation-ownership step (`stepOrder=0`, now owned by the
  `reception` role by default), this filter is removed — any active host
  employee visible at the branch can be nominated, since the real host is
  normally not a reception-role holder. Later workflow-level steps keep
  today's role-filtered behavior unchanged.
- **Notification-center addressing**: `NotificationCenterItem` and the
  Firebase push payload consumer gain a way to distinguish a role-addressed
  notification ("New invitation for Front Office") from a person-addressed
  one ("Delegated to you"), driven by the new `assignedRoleId`/
  `assignedUserId`/`reason` fields the API adds to the push payload.
  `NotificationBell` renders the two differently (e.g. a role badge vs. a
  "delegated to you" tag).
- **Branding**: a new VMSS/VMMS logo asset (produced alongside this change,
  see companion API change) is added to `src/assets/` and placed in the
  sidebar/topbar chrome (`AdminSidebar`/`AdminTopBar` or equivalent) and on
  the login pages, replacing today's plain `<title>VMSS</title>`-only
  branding with no logo anywhere in the app shell.

## Capabilities

### New Capabilities
(none — every change here modifies an existing capability's requirements)

### Modified Capabilities
- `visitor-request-wizard`: Visit Info step no longer requires or collects a
  host or a department; both requirements are removed. `staff-visitor-
  registration` needs no separate delta for this part — its spec already
  defers Visit Info validation wholesale to this capability ("Later steps
  apply the same rules as the self-service wizard"), so this one change
  covers both wizards.
- `staff-dashboard`: adds the Edit Invitation action and its field-level
  read-only/editable rules; changes Delegate's host-list filtering for the
  ownership step.
- `admin-invitations`: mirrors the staff-dashboard board behavior changes
  above (it already defers to staff-dashboard's card behavior for existing
  actions).
- `push-notifications`: notification payload/center item gains
  role-vs-person addressing and the bell renders it. **Sequencing note**:
  this capability has not yet been archived into `openspec/specs/` (its own
  change, `push-notifications`, is still pending archive) — this change's
  delta targets it as if already merged; reconcile the two before/at archive
  time if they haven't landed in the order assumed here.
- `app-shell`: adds the logo asset to sidebar/topbar and login-page chrome.

## Impact

- **Code**: `src/presentation/pages/visitor-request/**`,
  `src/presentation/pages/staff-visitor-registration/**`,
  `src/presentation/components/invitation-board/**` (new Edit modal,
  `DelegateInvitationModal` filter change), `src/presentation/hooks/
  use-invitations-board.ts`, `src/domain/entities/invitation-detail-schema.ts`,
  `src/presentation/components/push-notifications/**`,
  `src/presentation/components/notification-bell/**`,
  `src/presentation/context/notification-center-context.tsx`,
  `src/assets/` (new logo), sidebar/topbar/login components.
- **API contract (breaking)**: stops sending `hostId`/`hostNameOrEmail` on
  invitation/walk-in creation; adds a new use-case for
  `PATCH /invitations/{id}/edit`; consumes new push-payload addressing
  fields. Must ship no earlier than the companion API change (the API change
  is backward-compatible for reads, but the web app must stop sending host
  fields at creation once the API stops accepting them).
- **Design/assets**: requires the new logo asset (SVG preferred, with a
  favicon-sized variant) before the branding task can complete.
