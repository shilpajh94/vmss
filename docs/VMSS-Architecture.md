# VMSS – Architecture Document

Nov 9, 2026

## Overview

VMSS is a multi-role visitor management web app: a single-page React front end (this repo, VMMS_WEB) that talks to a separate REST backend (VMMS_API) over HTTPS. It covers visitor self-service requests, host and approver workflows, reception check-in and badge printing, kiosk and security-device management, zones, audit and emergency views.

| Area | Choice |
| --- | --- |
| UI | React 19, TypeScript, Vite 8 |
| Routing | react-router 8 (lazy-loaded pages, permission-guarded routes) |
| Styling | Tailwind CSS v4, tokens in `src/styles/theme.css` (`@theme`, `--color-*`), light and dark mode |
| Validation | Zod 4 schemas for every API payload |
| Charts / DnD | Recharts; dnd-kit (form builder reordering) |
| Push | Firebase Cloud Messaging (web push, device token registered with the API) |
| Serving | Static build behind nginx (Docker); no reverse proxy, browser calls the API cross-origin |
| Quality | oxlint plus brand, grid-span and theme-colour checks; Node unit tests; Playwright (Python) e2e in Docker |
| Specs | OpenSpec capability specs under `openspec/specs/` (35 capabilities) |

## Layered architecture

The front end follows clean architecture: dependencies point inward, and only the composition root knows concrete classes.

| Layer | Path | Responsibility | May import |
| --- | --- | --- | --- |
| Domain | `src/domain/` | Zod schemas and `z.infer` types for every wire payload (46 entities). No React. | nothing else |
| Data | `src/data/` | `api/` (ApiClient, `API_ENDPOINTS`), `repositories/` (port interfaces), `use-cases/` (one class per scenario, about 135). | domain |
| Infrastructure | `src/infrastructure/` | Adapters that implement the ports by calling `ApiClient.makeRequest` with an endpoint and a schema; Firebase setup. | data, domain |
| Presentation | `src/presentation/` | Pages, components, hooks, context, route permissions. Reaches the backend only through use cases. | data, domain |
| Composition root | `src/composition-root.ts` | Lazy `createApp()` wiring ApiClient, adapters and use cases; exposes `AppDependencies`. | everything |

Rules enforced by convention and review:

- `domain` never imports `data`, `infrastructure` or `presentation`.
- `data` never imports `infrastructure` or `presentation`.
- Presentation never calls `fetch` or `ApiClient`; it calls `useAppDependencies()` and then a use case's `execute`.
- All HTTP goes through `ApiClient`; every response is parsed with its Zod schema, so a wrong shape fails loudly as a `ZodError`.

## Folder structure and module map

Pages live in `src/presentation/pages/<feature>/`, each with its route component, a `hooks/` folder for orchestration and a `Components/` folder for page-only UI. Shared UI sits in `src/presentation/components/`.

| Surface | Routes | Page folders |
| --- | --- | --- |
| Public visitor portal | `/`, `/visitor/request`, `/visitor/track`, `/badge/scan` | visitor-portal-landing, visitor-request (OTP, wizard, history), visitor-track, badge-scan |
| Auth | `/admin/login` (password), `/staff/login` (SSO) | staff-login, staff-sso-login |
| Admin set-up | `/admin/organisation-configs`, branches, buildings, floors, departments, host-employees, visitor-categories, workflows, roles, form-builder, zones | admin-* |
| Devices | `/admin/kiosks`, `/admin/reception-desks`, `/admin/security-gates` | admin-kiosks, admin-devices, admin-reception-desks, admin-security-gates |
| Operations | `/admin/dashboard`, `/admin/invitations`, `/admin/audit-trail`, `/admin/emergency-inside`, calendar | admin-dashboard, admin-invitations, admin-audit-trail, emergency-inside, calendar |
| Staff / reception | `/staff/dashboard`, `/staff/invitations`, `/staff/calendar`, `/staff/visitors/new`, `/reception/dashboard`, `/reception/badge-printing` | staff-dashboard, staff-invitations, staff-visitor-registration, reception-dashboard, reception-badge-printing |

Other top-level folders: `src/assets/` (icons barrel), `src/styles/`, `openspec/` (specs and change proposals), `e2e/`, `tests/unit/`, `scripts/` (lint checks, screenshots, bundle budget), `CI-CD/` (pipelines for dev, stage and prod).

## API layer, composition root and dependency injection

A call from a button to the backend passes through six steps:

1. A page hook gets a use case from `useAppDependencies()` and calls `execute(...)` inside `useCallback`.
2. The use case delegates to a repository port (an interface in `src/data/repositories/`).
3. The adapter in `src/infrastructure/` implements that port and calls `apiClient.makeRequest({ endpointConfig, body, queryParams, parserSchema })`.
4. `ApiClient` builds the URL from `VITE_API_BASE_URL` plus the endpoint path and query string, and sends JSON.
5. If the endpoint has `hasToken: true`, it adds `Authorization: Bearer` from `sessionStorage["token"]`, and throws before `fetch` if no token exists.
6. The response is parsed with the Zod schema and returned typed, or a `ZodError` is raised.

`API_ENDPOINTS` in `src/data/api/api-endpoints.ts` is the single registry (about 135 entries). Each has `endpoint`, `method` and `hasToken`, with UPPER_SNAKE keys such as `LIST_KIOSKS`, `APPROVE_DEVICE`, `SET_INVITATION_ZONES`.

`createApp()` in `composition-root.ts` resolves lazily with `??=`: `resolveApiClient`, then each repository adapter, then each use case. `AppDependenciesProvider` exposes the result, so there are no global singletons. Environment config is one variable, `VITE_API_BASE_URL` (API origin plus prefix, no trailing slash), baked into the bundle at build time; Firebase keys are `VITE_*` too.

## Key flows

**Authentication and permissions.** Admins sign in with a password at `/admin/login`; other staff will use SSO at `/staff/login`. The token is held in `sessionStorage` only. Every protected route is wrapped in `RequirePermission` using the map in `route-permissions.ts` (for example kiosks need `kiosks:manage`, badge printing `visitors:print_badge`, zones `zones:view` or `zones:manage`). Sidebars read the same map, so they hide pages a user cannot open. Roles and permissions are editable under `/admin/roles`. Branch-scoped requests carry an `X-Branch-ID` header; kiosks and organisation-wide settings do not.

**Visitor request.** Visitors open `/visitor/request`, verify by OTP (mobile or email), and see prior history and a prefilled profile if they have visited before. The wizard's steps, order and fields come from the branch's published form configuration (form builder), not from code, so admins can add, hide and reorder steps. Submitting creates an invitation, tracked later at `/visitor/track`.

**Approval.** Each visitor category can have a multi-level workflow (level 0 is Reception). Approvers approve, deny, delegate or revert a step; the next level opens on approval. Hosts and staff can also register walk-in visitors at `/staff/visitors/new`.

**Check-in and badge.** Reception searches visits, verifies ID, uploads a photo, prints or reprints the badge, and checks the visitor out. A signed QR on the badge works at `/badge/scan` to check in, check out or re-enter without a staff login. Badge printing can be switched on and can require ID verification in organisation settings.

**Kiosks and devices.** Two different things share the word device:

- A **kiosk** record (`/admin/kiosks`) is a company-wide named check-in point with a description, an active flag and a hidden flag.
- A **managed device** (`/devices`) is a physical tablet that registers itself with an operating mode of `kiosk` (shown under Reception Desks) or `security` (Security Gates). A new device starts as pending and is approved by an admin, who can later enable, disable or delete it. A setting, kiosk location validation, makes kiosks enforce that they are at the expected location.
- Browsers also register an FCM token (`/notifications/devices`) for push notifications; that is separate from managed devices.

**Zones and emergency.** Zones limit where a visit may go and are set per visitor category and per invitation. The emergency view lists who is currently inside.

**Notifications and audit.** A bell shows unread counts with live refresh and push; the audit trail lists actions and can produce downloadable reports.

## Front end and backend integration, build and deployment

**Integration contract.** The backend (VMMS_API, a separate repo and deployment) is the source of truth. The front end mirrors its JSON in Zod schemas, so a backend change shows up as a parse error in one adapter rather than a silent bug. The backend must allow CORS from the web origin, including custom headers such as `X-Branch-ID`. Known gaps are tracked in the project notes (for example, audit-report download CORS on stage).

**Environments.** Dev, stage and prod each have a pipeline under `CI-CD/` that builds the Docker image and pushes it; `VITE_API_BASE_URL` differs per environment and is fixed at build time.

**Commands.**

| Command | Purpose |
| --- | --- |
| `npm run dev` | Vite dev server on port 5173 |
| `npm run build` | Type-check with `tsc -b`, then Vite build |
| `npm run build:check` | Build plus bundle-size budget check |
| `npm run lint` | oxlint plus brand, grid-span and theme-colour checks |
| `npm test` | Node unit tests in `tests/unit/` |
| `npm run e2e` | Playwright e2e suite in Docker against a running API |

**Runtime.** The container serves the static bundle with nginx: hashed assets cached for a year, `index.html` as the SPA fallback, and a `/health` endpoint for the orchestrator.
