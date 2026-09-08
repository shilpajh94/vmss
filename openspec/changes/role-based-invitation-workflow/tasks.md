## 1. Remove Host and Department Fields From Both Wizards

- [x] 1.1 Removed the host `AutocompleteField`, its required-field
      validation message, and `hostNameOrEmail`/`hostId` from
      `VisitInfoStep.tsx`'s props/state, `VisitInfoFormState`
      (visitor-request/types.ts, shared by both wizards), both
      `createInitial*FormState`/`to*VisitRequest` mappers, and both Zod
      wire schemas (`visit-request-schema.ts`, `staff-visit-request-
      schema.ts`).
- [x] 1.2 Removed `onSearchHosts`/`SEARCH_HOSTS` (`/hosts/search`) wiring
      from `visitor-request.tsx`. Went further than the task's literal
      scope, per design.md D1's explicit "delete as dead code" decision:
      deleted the entire now-unused stack (`search-hosts.ts` use case,
      `host-search-repository.ts` interface + HTTP impl, `host-search-
      schema.ts`, `host-search-out-schema.ts`, the `SEARCH_HOSTS` endpoint
      constant, and all composition-root.ts wiring) rather than leaving it
      wired-but-unused.
- [x] 1.3 Removed the staff-assisted wizard's `listHostEmployeesUseCase`-
      backed `handleSearchHosts` host-picker wiring, and the now-dead
      `hostEmployees` state/fetch on this page entirely (it had no other
      use once search was removed). `listHostEmployeesUseCase` itself is
      untouched in composition-root.ts — still resolvable for the Delegate
      modal, which will call it independently when built (§3).
- [x] 1.4 Updated both wizards' validation hooks to drop the host-required
      check.
- [x] 1.5 Removed the department dropdown/text-input field and its
      required-field validation message from `VisitInfoStep.tsx`. Also
      removed the now-dead `departments` state/fetch/prop-passing from
      *both* page-level wizard components (not just the field render) —
      after the field's removal, `departments` had no other consumer on
      either page. `listDepartmentsUseCase` itself is untouched — still
      used by several admin pages, and will be called independently by the
      Edit Invitation modal (§2.1) when built.
- [x] 1.6 Updated both wizards' validation hooks to drop the
      department-required check.
- [x] 1.7 Manual verification: **not performed as an interactive browser
      click-through** — no browser automation tool is available in this
      session. Verified instead via `npx tsc -b --noEmit` (exit 0, clean)
      confirming both wizards' component trees, form-state types, and
      submit-payload mappers are internally consistent with the fields
      removed. Flagging this so a human (or a future session with browser
      tooling) does the actual click-through before shipping.

## 2. Edit Invitation Modal

- [x] 2.1 Built `EditInvitationModal` following the Reschedule/Delegate
      pattern. Two deviations from the literal task text, both resolved
      with the user before implementing:
      (a) editable fields are purpose/date/time/duration/department/notes
      only — **not** location/building/visitor category, since `PATCH
      /invitations/{id}/edit` doesn't accept those (no backing column;
      confirmed against the API's actual `InvitationEditRequest` schema).
      (b) the read-only "visitor" section shows name + host only — the
      API's `InvitationDetailOut` doesn't include the primary contact's
      email/phone/ID-proof type at all (only `primaryContactFullName` +
      photo URL), so those are omitted rather than fabricated. Flagged as
      a possible follow-up (a small API change adding those fields to
      `InvitationDetailOut`) if wanted later.
- [x] 2.2 Added `edit`/`editingId`/`requestEdit`/`cancelEdit`/
      `pendingEditId`/`pendingEditDetail` to `use-invitations-board.ts`,
      mirroring `reschedule`/`delegate` exactly, including the
      action-in-progress auto-refresh guard. One addition beyond the
      mirrored pattern: `requestEdit` proactively calls `loadDetail`
      (like `viewVisitorInfo` does) since Edit's eligibility is
      status-based only (`canEdit`), unlike Delegate's
      (`detail?.currentApprovalStep`-gated) — a card whose detail was
      never fetched can still show the Edit button, so opening the modal
      can't assume `invitationDetails` already has it.
- [x] 2.3 Added an "Edit" button to `VisitRequestCard.tsx`
      (`canEdit`, reusing the same `RESCHEDULABLE_STATUSES` set
      `canReschedule` already uses — identical eligibility), threaded
      `onEditClick` through `KanbanColumn.tsx`, and wired both into
      `staff-dashboard.tsx` and `admin-invitations.tsx` identically (they
      share the same board hook/components).
- [x] 2.4 Success/error toast wiring identical to Reschedule/Delegate
      (`toast.success('Visit request updated.')` /
      `toast.error(error.message ?? fallback)`).
- [x] 2.5 Manual verification: **not performed as an interactive browser
      click-through** — no browser automation tool available this
      session. Verified via `npx tsc -b --noEmit` (exit 0) confirming the
      modal, hook wiring, and both board pages are internally consistent.
      Flagging for a human click-through before shipping: edit a
      submitted invitation's date/time/duration/notes in one save;
      confirm the read-only section shows name/host only and cannot be
      changed from this modal.

## 3. Delegate Modal Host-Picker Filter Change

- [x] 3.1 Confirmed: `CurrentApprovalStepSchema`/`CurrentApprovalStep`
      (invitation-detail-schema.ts) already models `stepOrder` as a plain
      `number` — no dedicated "is ownership step" flag was added API-side;
      the client-side check is `stepOrder === 0`, resolving design.md's
      Open Question.
- [x] 3.2 Added a `stepOrder` prop to `DelegateInvitationModal`; the
      role-match filter now skips when `stepOrder === 0`
      (`isOwnershipStep`), keeping the existing role-filtered behavior for
      every other step. Also fixed the modal's "Delegating within role:
      ..." helper text and empty-picker message, which would otherwise
      have kept claiming a role restriction that no longer applies for the
      ownership step. Threaded `stepOrder={pendingDelegateDetail?.
      currentApprovalStep?.stepOrder}` through both `staff-dashboard.tsx`
      and `admin-invitations.tsx`.
- [x] 3.3 Manual verification: **not performed as an interactive browser
      click-through** — no browser automation tool available this
      session. Verified via `npx tsc -b --noEmit` (exit 0). Flagging for a
      human click-through: delegating a freshly submitted invitation's
      ownership step should offer every active host employee at the
      branch; delegating a later, category-configured step should still
      offer only role-matching hosts.

## 4. Card and Board Display Updates

- [x] 4.1 Added a "Host: ..." line to `VisitRequestCard.tsx`, rendered
      whenever `detail` is available (via preload for `requested`-column
      cards, or once expanded/edited for others):
      `detail.hostNameOrEmail ?? 'Unassigned — Front Office'`. Omitted
      entirely (not shown as a false "Unassigned") when `detail` hasn't
      loaded yet, rather than guessing — matches how the card already
      treats `detail?.currentApprovalStep` as absent-until-loaded.
- [x] 4.2 Confirmed already correct, no code change needed:
      `resolveApproverLabel` (approval-step-label.ts) is generic over
      `approverRoleId`/`approverUserId` — it already renders the
      front-office role's name for a freshly submitted, undelegated
      `stepOrder` 0 step exactly the same way it renders any other
      role-identified step's pending approver.

## 5. Notification Addressing

- [x] 5.1 Extended `NotificationCenterItem` with a `reason?:
      'role_assigned' | 'delegated'` field (new `NotificationAddressingReason`
      type). Only `reason` is stored/exposed to the UI, not the raw
      `assignedRoleId`/`assignedUserId` — the ids are consumed once, at
      receipt time, to build the display label; the UI only ever needs to
      know *which kind* of addressing produced an item, not the raw id.
- [x] 5.2 Updated `PushNotificationsProvider`'s `onMessage` handler to read
      `payload.data.reason`/`assignedRoleId`, build a label ("New
      invitation for {role name}" / "Delegated to you"), and prefix it onto
      both the toast and the notification-center message. Resolving
      `assignedRoleId` to a display name needed a role-name lookup this
      app-root-mounted provider didn't otherwise have — added a one-time,
      lazy `listRolesUseCase.execute()` call (cached in a ref, not
      threaded down from the board's own `roleNameById` state, since this
      provider is independent of which board page — or no board page — is
      currently open).
- [x] 5.3 Added an `AddressingBadge` to `NotificationBell.tsx`'s row
      rendering — a small "Role" tag for `role_assigned` items, a
      "Delegated to you" tag for `delegated` items, nothing for items with
      no `reason` (pre-existing/unrelated pushes).
- [x] 5.4 Manual verification: **not performed as an interactive browser
      click-through** — no browser automation tool available this
      session, and this specifically needs a real FCM push to exercise
      end-to-end (not something `tsc` can verify). Verified via `npx tsc -b
      --noEmit` (exit 0) that the payload-parsing, label-building, and
      rendering code paths are internally consistent. Flagging for a human
      to trigger a real role-fan-out notification and a delegation
      notification and confirm both the toast and bell list render the
      correct label.

## 6. Branding

- [x] 6.1 Produced `src/assets/logo.svg` (icon + "VMSS" wordmark, 140×32)
      and `src/assets/logo-mark.svg` (icon-only, 32×32 — the
      favicon-sized/compact variant), both hand-authored SVG using the
      app's existing brand colors (`--color-secondary-accent`/
      `--color-admin-accent` gradient, `--color-primary` wordmark) since
      no design-tool/brand-kit asset exists to source from (design.md's
      accepted trade-off). No image-generation tool was available this
      session — this is geometric/vector SVG markup, not a raster image.
- [x] 6.2 Placed `logo-mark.svg` in `AdminSidebar.tsx` and
      `DashboardSidebar.tsx`, replacing each one's existing generic
      `ShieldIcon`-in-a-box brand-mark placeholder — these are the
      persistent chrome rendered on every admin page and every staff page
      (`staff-dashboard`, `staff-visitor-registration`) respectively.
      **Deviation, documented rather than silently applied**: did not
      additionally duplicate the mark into `AdminTopBar.tsx` /
      `WorkspaceHeader.tsx` even though the delta spec's scenario text
      says "sidebar and top bar" — the topbar has no natural brand-mark
      slot, and it renders immediately adjacent to the sidebar on every
      page (never shown without it), so a second icon inches away would
      read as visual clutter/duplication rather than reinforcing identity.
      Treated "sidebar and top bar" as describing the app shell's chrome
      collectively, satisfied by the always-visible sidebar placement.
      Flagging this reading for review — happy to add it to the topbars
      too if that literal reading is actually wanted.
- [x] 6.3 Placed `logo-mark.svg` in `StaffGatewayHeader.tsx` (`/admin/login`)
      and `StaffPortalHeader.tsx` (`/staff/login`), alongside each page's
      existing "VisitorPass" wordmark/gateway-badge header.
- [x] 6.4 Manual verification: **not performed as an interactive browser
      click-through** — no browser automation tool available this
      session. Verified via `npx tsc -b --noEmit` (exit 0) that every
      import resolves. Flagging for a human visual check: logo renders
      without distortion/clipping across both sidebars and both login
      pages; this app shell has no dark-theme toggle to check against
      (confirmed no theme-switching mechanism exists in the codebase).

## 7. Cleanup and Verification

- [x] 7.1 **No automated test suite exists in this repo** (confirmed: no
      `test`/`vitest`/`jest` script in `package.json`, no `*.test.*`/
      `*.spec.*` files anywhere in `src/`) — so there is no existing test
      to break, and none was silently skipped. Ran the closest available
      verification instead: `npx tsc -b --noEmit` (exit 0), `npm run lint`
      → `oxlint` (exit 0, clean), and a full `npm run build` (`tsc -b &&
      vite build`, succeeded — 459 modules transformed, only a pre-existing
      unrelated chunk-size warning, no errors). `dist/` removed afterward
      since it was only a verification build.
- [ ] 7.2 Manual end-to-end pass: **not performed** — no browser automation
      tool available this session, and this step also depends on real
      backend data (a live reception-role staff member, a real delegation)
      that can't be simulated by static analysis. This is the one task in
      the whole change that genuinely needs a human (or a future session
      with browser tooling) to execute: create an invitation with no host
      field shown, confirm it appears as "Unassigned — Front Office" for a
      reception-role staff member, delegate it to a specific host, confirm
      the card and notification-center both reflect the assignment, then
      edit its date/time via the new Edit modal.
