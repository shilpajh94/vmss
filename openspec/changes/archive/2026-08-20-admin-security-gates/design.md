## Context

See proposal.md - Why. This capability follows the same admin CRUD pattern as `admin-reception-desks` (spec-per-screen, `data/` → `infrastructure/` → `presentation/` layering per `.claude/rules/clean-architecture.md` and `.claude/rules/data-api-layer.md`), reusing `Building` and `Floor` as relation targets exactly as reception desks does. `AdminSidebar` already reserves the `security-gates` nav key, label, and icon; `AdminTopBar` only accepts `description`/`breadcrumb`/`currentUser` and hardcodes the "Organization Admin" heading — this capability reuses it as-is, same as every other admin screen (the Figma frame's "Access Control Admin" heading is not introduced as a new `AdminTopBar` capability).

## Goals / Non-Goals

**Goals:**
- Deliver the Security Gates & Turnstiles Register (list) and Register/Edit Gate pages matching the Figma design (node `203:1418`) and the existing admin CRUD architecture.
- Support a four-state gate type (Bidirectional / Entry Only / Exit Only / High Security) and a three-state connectivity status (Online / Maintenance / Offline) as two independent enums.
- Support a Building → Floor cascading dropdown in the form, reusing the exact pattern already built for `admin-reception-desks`.

**Non-Goals:**
- Real filtering behind the "Filters" button (matches every existing admin screen).
- Live/real-time connectivity monitoring (e.g. polling actual hardware state). Connectivity status is an admin-set field on the record, not a live telemetry feed.
- Modeling auth method as a structured/enumerated set of authentication factors. The Figma design shows free-form combinations ("Biometric / RFID Card", "LPR / PIN Override", "Retina + SmartCard", "No Authentication Required"), so Auth Method is a single optional free-text field, matching how Reception Desk's Operating Hours are handled.
- Any change to Building or Floor CRUD screens themselves.

## Decisions

- **Gate Type modeled as a single flat enum, not split into direction + security-level dimensions**: the Figma design renders "Bidirectional", "Entry Only", "Exit Only", and "High Security" as four values of one badge column, even though "High Security" reads as a different axis (security level) than the other three (traffic direction). This design faithfully mirrors the source screen rather than introducing a two-dimensional model the design doesn't show. `SecurityGateSchema.gateType: z.enum(["bidirectional", "entry_only", "exit_only", "high_security"]).default("bidirectional")`.
- **Connectivity as its own three-state enum, separate from Gate Type**: `connectivityStatus: z.enum(["online", "maintenance", "offline"]).default("online")`, structurally identical to `ReceptionDesk.status` but a distinct field/domain (hardware link state, not desk operational state) — kept as its own enum rather than reusing `ReceptionDesk`'s type, since the two entities are unrelated.
- **No assigned-personnel field**: unlike Reception Desk, the Figma design carries no personnel/owner column for gates, so `SecurityGateSchema` has no receptionist-equivalent field.
- **Denormalized display fields on the read model**: like `ReceptionDesk.buildingName`/`floorName`, `SecurityGate` carries `buildingName` and, when present, `floorName` (backend-resolved) so the table renders without an extra client-side join. `SecurityGateInput = Omit<SecurityGate, "id" | "buildingName" | "floorName">` carries only ids for create/update.
- **Floor field cascades from Building**: identical approach to `admin-reception-desks` — load buildings and floors up front, filter Floor options client-side to the selected building, clear `floorId` on building change.
- **New endpoints follow the existing REST shape**: `LIST_SECURITY_GATES`/`CREATE_SECURITY_GATE` at `/security-gates`, `UPDATE_/DELETE_SECURITY_GATE` at `/security-gates/:id`, all `hasToken: true`, mirroring the reception-desk endpoints.

## Risks / Trade-offs

- [Gate Type conflates direction and security-level semantics into one enum] → Accepted as a faithful rendering of the source design; if the backend later needs to reason about these as separate concerns, splitting the field is a follow-up change, not a blocker here.
- [Floor list not scoped server-side to a building] → Same mitigation as `admin-reception-desks`: client-side filtering on the already-fetched full floor list.
- [Connectivity status is admin-editable, not live hardware telemetry] → Explicitly a Non-Goal; if real-time gate health becomes a requirement, that's a separate capability layered on top of this record.
