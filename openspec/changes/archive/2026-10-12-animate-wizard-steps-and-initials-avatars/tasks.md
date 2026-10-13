## 1. Shared avatar and initials

- [x] 1.1 Update `src/presentation/utils/initials.ts` so `initialsFor` trims, splits on `/\s+/`, and returns the uppercased first letters of the first two words (`""` for an empty name). Refresh its comment to say it is the app-wide rule.
- [x] 1.2 Create `src/presentation/components/ui/Avatar.tsx` (`name`, `photoUrl?`, `size: 'sm' | 'md'`, `className?`, `style?`): photo with `onError` → initials fallback, reference initials style by default, initials span `aria-hidden`.
- [x] 1.3 Replace the blank grey circles with `<Avatar>` in `HostEmployeesTable.tsx` (`size="md"`, `photoUrl={hostEmployee.avatarUrl}`), `RecentCheckinsCard.tsx` (`size="sm"`), and `UpcomingVisitorsCard.tsx` (`size="sm"`).
- [x] 1.4 Switch `VisitorInfoModal.tsx` to the shared `Avatar` (keeping its tone classes via `className`) and delete its private `Avatar` and `initialsFor`.
- [x] 1.5 Switch `VisitRequestCard.tsx` to the shared `Avatar` (keeping its hashed tint via `style`) and delete its private `initialsFor`.
- [x] 1.6 Switch the top bars (`RegistrationWorkspaceHeader`, `WorkspaceHeader`, `ReceptionTopBar`, `AdminTopBar`) to `<Avatar>`. The staff bars already use the reference style and stay unchanged; the admin and reception bars move from grey initials to the reference style.

## 2. Shared step motion

- [x] 2.1 In `src/styles/index.css`, add the `--step-motion-duration` / `--step-motion-ease` tokens, the `.step-enter` keyframes for `data-direction="forward"`/`"backward"` (`translateX` ±24px + opacity), and a reduced-motion block that zeroes the duration and disables `.step-enter`.
- [x] 2.2 Add `src/presentation/hooks/use-step-direction.ts` returning `'forward' | 'backward' | 'none'` from the previous vs current step index.

## 3. Staff Register Visitor

- [x] 3.1 `RegistrationStepper.tsx`: turn each connector into a track plus an inner fill bar (`scaleX` 0→1 when `index < currentStep`, `origin-left`), animate circle colour, and crossfade the number to a `CheckIcon` for completed steps, all using the shared tokens.
- [x] 3.2 `staff-visitor-registration.tsx`: wrap the step chain in `<div key={currentStep} className="step-enter" data-direction={direction}>`, and add `overflow-x-clip` to the form card.

## 4. Public visitor wizard

- [x] 4.1 `StepSidebar.tsx`: add a vertical connector between steps with a `scaleY` fill (`origin-top`) for completed steps, plus the same circle colour transition and checkmark crossfade as the staff stepper.
- [x] 4.2 `StepProgressHeader.tsx`: point the progress bar's width transition at the shared duration/easing tokens.
- [x] 4.3 `visitor-request.tsx`: wrap the step chain in the same keyed `.step-enter` wrapper with `data-direction`, and add `overflow-x-clip` to the content card.

## 5. Verification

- [x] 5.1 `npm run lint` and `npm run build` clean.
- [x] 5.2 Staff wizard at 1920 and 1024 widths: Next fills the connector, shows a checkmark on the completed step, and slides content in from the right. Picking an earlier step reverses with a slide from the left. A failed Next plays nothing. Inputs accept typing immediately after a step change.
- [x] 5.3 Visitor wizard at desktop and 375px: the sidebar's connector and checkmark animate, the phone progress bar animates its width, and the content slides in both directions.
- [x] 5.4 With reduced motion emulated (Playwright `reduced_motion="reduce"`): both wizards change step instantly with correct states.
- [x] 5.5 Avatars: the Host Employees, Recent Check-ins (admin and reception) and Upcoming Visitors lists show initials (or a photo where an employee has one). A broken photo URL falls back to initials. Staff top bars and visit cards look unchanged apart from the unified initials; admin and reception top-bar badges now use the reference style.
