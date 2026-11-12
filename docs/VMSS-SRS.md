# VMSS – Software Requirements Specification (SRS)

Version 1.0 draft, Nov 9, 2026. Derived from the implemented front end (VMMS_WEB) and its OpenSpec specs in `openspec/specs/`. Backend behaviour is described only as far as the front end depends on it.

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements of the Visitor Management System (VMSS) web application, for developers, testers and stakeholders.

### 1.2 Scope
VMSS lets organisations pre-register and receive visitors, route visit requests through multi-level approval, check visitors in and out with badges, manage kiosks and security devices, restrict access by zone, and audit all activity. It is a browser-based single-page app that talks to a separate REST API (VMMS_API).

### 1.3 Definitions

| Term | Meaning |
| --- | --- |
| Invitation / visit request | A record of a planned or walk-in visit |
| Host | Employee being visited |
| Approver | Person who decides an approval step |
| Kiosk | Company-wide named self-service check-in point (admin record) |
| Managed device | Physical tablet registered in `kiosk` or `security` operating mode |
| Zone | Restricted area a visit may be limited to |
| Form builder | Admin tool defining the visitor form's steps, groups and fields |
| OTP | One-time code used to verify a visitor's mobile or email |

## 2. Overall description

### 2.1 Product perspective
React single-page application (React 19, TypeScript, Vite) served as static files by nginx. All data comes from VMMS_API over HTTPS with a bearer token. Push notifications use Firebase Cloud Messaging.

### 2.2 User classes

| User class | Authentication | Description |
| --- | --- | --- |
| Visitor | OTP, no account | Requests and tracks visits, uses badge |
| Host / staff | Login (SSO planned) | Registers and follows visits |
| Approver | Login | Decides approval steps |
| Reception | Login | Checks visitors in and out, prints badges |
| Admin | Password login | Configures the organisation |

Roles and their permissions are configurable by an admin; the permission codes in section 4 gate each feature.

### 2.3 Operating environment
Current evergreen desktop and mobile browsers; responsive layout; light and dark themes. Deployed per environment (dev, stage, prod) as a Docker image.

### 2.4 Constraints and assumptions
- The API base URL is fixed at build time (`VITE_API_BASE_URL`).
- The API must allow CORS from the web origin, including the `X-Branch-ID` header.
- The session token lives in `sessionStorage` only.
- Staff SSO depends on a tenant identity provider and is not yet generally enabled.

## 3. System architecture requirements

- AR-1. Code is layered presentation, data, domain and infrastructure; dependencies point inward.
- AR-2. The UI reaches the backend only through use cases obtained from `useAppDependencies()`.
- AR-3. All HTTP goes through `ApiClient`, using endpoints registered in `API_ENDPOINTS`.
- AR-4. Every API response is validated with a Zod schema; a mismatch is an error, not silently accepted.
- AR-5. Concrete implementations are wired only in `composition-root.ts`, lazily.

## 4. Functional requirements

Permission codes are those in `src/presentation/route-permissions.ts`.

### 4.1 Authentication and access control (FR-AUTH)
- FR-AUTH-1. An admin shall sign in with email and password at `/admin/login`.
- FR-AUTH-2. Staff shall be able to sign in by SSO at `/staff/login`; returning from the identity provider completes sign-in, and failure shows an error without a stuck loading state.
- FR-AUTH-3. Protected pages shall redirect to login when there is no token or the API returns 401.
- FR-AUTH-4. Each protected route shall require its permission; menus shall hide entries the user cannot open.
- FR-AUTH-5. A signed-in user shall be able to sign out from the top bar, which clears the token.
- FR-AUTH-6. Admins shall create and edit roles and their permissions at `/admin/roles` (`roles:manage`).

### 4.2 Visitor self-service (FR-VIS)
- FR-VIS-1. A visitor shall verify their mobile number or email by OTP before the request wizard opens.
- FR-VIS-2. The wizard's steps, order, labels and fields shall come from the branch's published form configuration; hidden steps are unreachable and progress counts reflect only active steps.
- FR-VIS-3. While the configuration loads, the wizard shall show a loading state rather than a default step list.
- FR-VIS-4. A returning visitor shall see their history and have name, email, phone, contact method and ID type prefilled; ID image and photo shall not be prefilled.
- FR-VIS-5. On submit, the system shall create an invitation and report success or the validation errors returned.
- FR-VIS-6. A visitor shall be able to track a request's status at `/visitor/track`.
- FR-VIS-7. A visitor shall be able to check in, check out or re-enter by badge code at `/badge/scan` without logging in.

### 4.3 Invitations and approval (FR-INV)
- FR-INV-1. Staff shall see invitations as cards with approval level, status, visitor, purpose and host, with search and filters (purpose, registration type, status, source).
- FR-INV-2. Opening a card shall show visitor information and the visit timeline.
- FR-INV-3. An approver shall approve or reject a step at their level; approval opens the next level, and the last approval releases the visit to reception.
- FR-INV-4. An approver shall be able to delegate a step and to revert an approval.
- FR-INV-5. Authorised users shall be able to reschedule and edit an invitation.
- FR-INV-6. Staff with `invitations:create` shall register a visitor at `/staff/visitors/new`, looking up existing visitors by email or phone.
- FR-INV-7. Authorised users shall export invitations as CSV or Excel, filtered by status and date range (`invitations:export`).
- FR-INV-8. A calendar shall show visits by day and as a feed (`invitations:view`).
- FR-INV-9. Admins shall see all invitations (`invitations:view-all`).

### 4.4 Reception, check-in and badges (FR-REC)
- FR-REC-1. Reception shall search visits and see recent check-ins.
- FR-REC-2. Reception shall verify visitor ID and upload a photo; organisation settings may require ID verification before printing.
- FR-REC-3. Users with `visitors:print_badge` shall print and reprint a visitor badge carrying a signed QR.
- FR-REC-4. Reception shall check visitors out and allow re-entry with the badge.
- FR-REC-5. Users with `emergency:view` shall see who is currently inside.
- FR-REC-6. Admins shall turn badge printing on or off and set whether it requires ID verification.

### 4.5 Organisation set-up (FR-ORG)
- FR-ORG-1. Admins shall list, create, edit and delete branches, departments, buildings, floors and visitor categories, with pagination and status filters, subject to each `:manage` permission.
- FR-ORG-2. Admins shall manage the host-employee directory (sync, enable, disable, assign or revoke host role) (`employees:manage`).
- FR-ORG-3. Admins shall define an approval workflow per visitor category with at least one level and an approver for each (`approval-workflow-rules:manage`).
- FR-ORG-4. Admins shall edit organisation configuration (`companies:manage`).
- FR-ORG-5. Admins shall build the visitor form: create, edit, reorder and delete steps, field groups and fields, and publish the configuration (`form-builder:manage`).
- FR-ORG-6. Admins shall define zones and assign them to visitor categories and to individual invitations (`zones:manage`; view needs `zones:view`).

### 4.6 Kiosks and devices (FR-DEV)
- FR-DEV-1. Admins shall list kiosks with pagination (default 20 per page, name ascending), filter by All, Active or Inactive, and sort by name or created date.
- FR-DEV-2. Hidden kiosks shall be excluded by default and shown, with a Hidden badge, when Show hidden is on.
- FR-DEV-3. Users with `kiosks:manage` shall add, edit, activate or deactivate, hide or unhide, and delete kiosks; view-only users see no write actions, and a 403 is reported.
- FR-DEV-4. Kiosk requests shall be company-wide and carry no `X-Branch-ID` header.
- FR-DEV-5. Reception Desks and Security Gates pages shall list managed devices filtered by operating mode `kiosk` or `security` (`desks:manage`, `gates:manage`).
- FR-DEV-6. A newly registered device shall be Pending; an admin shall approve it, then enable, disable or delete it, as allowed by the device's `canApprove`, `canEnable` and `canDisable` flags.
- FR-DEV-7. Admins shall switch kiosk location validation on or off.
- FR-DEV-8. The browser shall register and unregister a push token with the API for notifications.

### 4.7 Dashboards, notifications and audit (FR-OPS)
- FR-OPS-1. Admin and staff dashboards shall show overview and analytics figures and refresh live.
- FR-OPS-2. Users shall see an unread notification count, list notifications, and mark one or all as read; push notifications deep-link to the relevant invitation.
- FR-OPS-3. Users with `audit-logs:view` shall browse the audit trail and request and download audit reports.

## 5. External interface requirements

- EI-1. Backend: REST/JSON over HTTPS, about 135 endpoints registered in `src/data/api/api-endpoints.ts`; bearer token where `hasToken` is true.
- EI-2. Firebase Cloud Messaging for web push.
- EI-3. Identity provider for staff SSO.
- EI-4. Badge printing through the browser's print facility.
- EI-5. Hardware: tablets running the kiosk or security mode, and a camera for visitor photos.

## 6. Non-functional requirements

| ID | Category | Requirement |
| --- | --- | --- |
| NFR-1 | Security | Token kept in `sessionStorage` only; no secrets in the bundle other than public `VITE_*` keys; permissions enforced by the API as well as hidden in the UI. |
| NFR-2 | Usability | Responsive from phone to desktop; light and dark theme; consistent loading, empty, error and toast states. |
| NFR-3 | Performance | Pages are lazy-loaded; production bundle must pass the budget check (`npm run build:check`). |
| NFR-4 | Reliability | Failed loads show an error with retry without a page reload; expired sessions redirect to login. |
| NFR-5 | Maintainability | Layered architecture; Tailwind v4 theme tokens only; icons from one barrel; lint checks for brand, grid spans and theme colours. |
| NFR-6 | Testability | Unit tests in `tests/unit/`; Playwright end-to-end suite in `e2e/`. |
| NFR-7 | Deployability | Static image served by nginx with SPA fallback, `/health` endpoint and long-lived caching of hashed assets; separate pipelines for dev, stage and prod. |
| NFR-8 | Compatibility | Evergreen browsers; exact support matrix to be confirmed. |

## 7. Known gaps and open items

- Staff SSO is not yet the standard login; admins use password login.
- Backend currently refuses re-delegation for host and reception roles.
- Invitation edit sends `customFields`, which the backend does not yet accept.
- Invitation detail lacks primary contact email and phone, and omits group-collected visitors and generic file-upload answers as URLs.
- Group submissions: the backend enforces some required fields even when hidden by a visibility condition.
- Audit report download on stage can be blocked by CORS.
- The public wizard deliberately sends no `consents` key.
- Not covered in this front-end repo: backend data model, database, and the kiosk device application itself.

## 8. Traceability

Each requirement group maps to OpenSpec capabilities in `openspec/specs/`:

| Requirements | Specs |
| --- | --- |
| FR-AUTH | staff-login, staff-sso-login, admin-roles, app-shell |
| FR-VIS | visitor-portal-landing, visitor-otp-verification, visitor-request-wizard, visitor-return-history, visitor-track-request |
| FR-INV | admin-invitations, staff-dashboard, staff-home-dashboard, staff-visitor-registration, staff-calendar, admin-approval-workflows |
| FR-REC | reception-dashboard |
| FR-ORG | admin-organisation-configs, admin-branches, admin-buildings, admin-floors, admin-departments, admin-host-employees, admin-visitor-categories, admin-form-builder |
| FR-DEV | admin-kiosks, admin-reception-desks, admin-security-gates |
| FR-OPS | admin-dashboard, dashboard-insights, notifications, live-data-refresh, admin-audit-trail |
| NFR | responsive-layout, design-theme, theme-mode, async-ui-states, ui-motion, brand-identity |
