## Context

See proposal.md. The app follows the clean-architecture rules in `.claude/rules/` (ports in `src/data/repositories`, adapters in `src/infrastructure`, use cases in `src/data/use-cases`, wiring only in `composition-root.ts`). Reception Desks and Security Gates currently have list pages plus Add/Edit forms backed by legacy desk/gate repositories. The Kiosks page uses `/kiosks` and stays unchanged. Role permissions are already managed via `LIST_PERMISSIONS` / role permission forms. Responses are camelCase inside the `{success, message, data}` envelope.

## Goals / Non-Goals

**Goals:**
- One shared device list implementation parameterized by `operatingMode`, used by both pages.
- Server flags (`canApprove/canEnable/canDisable`) drive buttons; the UI adds permission gating on top.
- Setting toggle and invitation-detail device display.

**Non-Goals:**
- Mobile registration and `device-id` header flows (no web caller).
- Touching `/kiosks` endpoints or the Kiosks page.
- Treating `deviceId` as authentication.

## Decisions

- **Single `DeviceRepository` port** (list, approve, enable, disable, delete) plus a `KioskLocationValidationSettingRepository` port. Alternative: separate repos per page; rejected since the endpoint is identical and only the filter differs. `register` is not added (no web use) to avoid dead code.
- **Shared hook `use-admin-devices(operatingMode)`** under a shared presentation location (e.g. `presentation/hooks`), with thin page wrappers in `admin-reception-desks` and `admin-security-gates` and a shared `DevicesTable` component. Alternative: duplicating hooks per page, rejected for drift.
- **Status filter modeled as a UI enum** (`pending | approved | disabled`) mapped to query params in one pure function, so the mapping is unit-testable.
- **Row updates use the returned device** to patch local state; 409 triggers a list refresh. Deletion refreshes and steps back a page if emptied.
- **Permission gating**: reuse how existing pages read the user's permissions; if no client-side permission source exists, gate on server 403s and surface them as permission errors. Confirm during implementation which source is available.
- **Legacy removal**: delete legacy desk/gate forms, hooks, use cases, repos, endpoints entries, and routes; legacy `/new` and `/:id/edit` routes redirect to the list. Alternative: keep dead code for rollback; rejected, git history suffices.
- **Setting placement**: a card on the existing Organisation Configs page (admin settings host) rather than a new page, since it is a single toggle.
- **Invitation detail**: add nullable `checkInDevice`/`checkOutDevice` objects `{id, deviceId, name, operatingMode}` to the schema (`.nullable().optional()` to tolerate older responses) and render in `VisitorInfoModal`.

## Risks / Trade-offs

- [Removing desk/gate management loses features such as floor/receptionist/gate type] → confirmed by the requester as replace; call out in release notes.
- [Admins without new permissions see no-access until the backend migration runs] → backend migration grants Admin roles; show clear permission messaging.
- [`/devices` sort keys are snake-ish (`created_at`, `approval_status`)] → map UI sort columns to exact values in one place.
- [Enable/disable race with another admin] → 409 handling plus list refresh.

## Migration Plan

Ship frontend after the backend migration is deployed. Rollback is a revert of this change; no client-side data migration.
