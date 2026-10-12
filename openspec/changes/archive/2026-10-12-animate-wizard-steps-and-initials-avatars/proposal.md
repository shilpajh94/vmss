## Why

Moving between registration steps is an instant swap today: the stepper circle changes colour and the form content is replaced, with no sense of moving forward. Separately, several lists show a person with no photo as a blank grey circle (employees table, Recent Check-ins, Upcoming Visitors). That reads as a missing image, while the top bars already show a clear initials badge (e.g. "AS") for the signed-in user.

## What Changes

**Step transitions (staff Register Visitor and public visitor wizard)**
- Moving forward fills the connector between the current and next step toward the next step. The circle being left animates to a "completed" state with a checkmark, and the next circle animates to "active".
- Moving back reverses this: the connector un-fills and the step returns to "active".
- The step's form content slides in from the right on Next and from the left on Back (or on picking an earlier step).
- The public wizard's desktop step sidebar gets the same completed-checkmark/active transitions, with a vertical connector filling down. Its phone progress bar already animates its width; it gets an explicit duration/easing so all three indicators share one motion timing.
- Every animation is disabled under `prefers-reduced-motion: reduce`. Content then swaps instantly and the stepper changes state without motion, as today.

**Initials avatars**
- A single shared avatar component shows a person's photo when one exists and loads. Otherwise it shows up to two initials in the reference style (light-blue tint, blue ring, bold blue letters, as in the top-bar "AS" badge).
- The blank grey circles in the Host Employees table, Recent Check-ins card (admin and reception dashboards) and Upcoming Visitors card are replaced with this avatar. Employees with an `avatarUrl` show their photo.
- The existing duplicated `initialsFor` helpers (VisitRequestCard, VisitorInfoModal, the top bars) are consolidated onto the one shared helper. Those surfaces keep their current look (including the visit card's tinted background); only the initials rule is unified, see Assumptions.

Assumptions:
- "Employees, visitors etc." means every place a person is shown with an avatar placeholder. Name-only cells (branch contact person, department head) keep no avatar.
- Initials are the first letters of the first two words of the name, matching the reference badge ("Aadarsh S Kumar" → "AS"). The visit card and visitor info modal currently use first + last word ("AK"); they switch to the same rule so a person reads the same everywhere.

## Capabilities

### New Capabilities
- `person-avatars`: how a person (employee, visitor, signed-in user) is represented when no photo is available, across lists and cards.

### Modified Capabilities
- `staff-visitor-registration`: adds a requirement for animated step transitions in the stepper and step content.
- `visitor-request-wizard`: adds the same step-transition requirement for the public wizard's sidebar, phone progress header, and step content.

## Impact

- New: a shared `Avatar` component under `src/presentation/components/`, plus step-transition CSS in `src/styles/index.css`.
- Changed: `RegistrationStepper.tsx`, `staff-visitor-registration.tsx`, `StepSidebar.tsx`, `StepProgressHeader.tsx`, `visitor-request.tsx`, `HostEmployeesTable.tsx`, `RecentCheckinsCard.tsx`, `UpcomingVisitorsCard.tsx`, `VisitRequestCard.tsx`, `VisitorInfoModal.tsx`, `utils/initials.ts`.
- No API, data, or dependency changes. Animations are CSS-only, with no animation library, consistent with `RouteTransition`.
