# VMSS – Feature Catalogue

Nov 9, 2026. Source: `src/App.tsx`, `src/presentation/route-permissions.ts`, `openspec/specs/`.

Pages need the listed permission; users without it do not see the menu entry and cannot open the route.

## 1. Public visitor portal (no login)

| Feature | Route | Description |
| --- | --- | --- |
| Landing page | `/` | Entry point: Request Visit, Track Request. |
| Visitor request wizard | `/visitor/request` | OTP verification (mobile or email), then a multi-step form. Steps, order and fields come from the branch's published form-builder configuration. |
| Returning-visitor history | `/visitor/request` | After OTP, shows past visits and prefills name, email, phone, contact method and ID type. ID image and photo must be re-uploaded. |
| Track request | `/visitor/track` | Look up the approval status of a submitted request. |
| Badge scan | `/badge/scan` | Enter or scan the badge's signed QR text to check in, check out or re-enter. |

## 2. Authentication

| Feature | Route | Description |
| --- | --- | --- |
| Admin password login | `/admin/login` | Email and password; token kept in `sessionStorage`. |
| Staff SSO login | `/staff/login` | Single sign-on through the tenant's identity provider (rolling out). |
| Sign out, session expiry | all | Sign out in the top bar; a 401 sends the user back to login. |

## 3. Host, staff and approver

| Feature | Route | Permission | Description |
| --- | --- | --- | --- |
| Staff dashboard | `/staff/dashboard` | | Visit cards with level badge (for example Level 1/2 Pending), filters, search. |
| Invitations | `/staff/invitations` | `invitations:view` | Own and relevant invitations. |
| Approve / Deny | invitation cards | | Act on a step at your level. |
| Delegate, revert | invitation cards | | Pass a step to someone else, or undo an earlier approval. |
| Reschedule, edit | invitation cards | | Change time or details of a visit. |
| Register visitor | `/staff/visitors/new` | `invitations:create` | Walk-in or pre-registered visit; look up an existing visitor by email or phone. |
| Calendar | `/staff/calendar` | `invitations:view` | Day pages and feed of visits. |
| Notifications | top bar | | Bell with unread count, mark read or mark all read, live refresh, web push. |

## 4. Reception

| Feature | Route | Permission | Description |
| --- | --- | --- | --- |
| Reception dashboard | `/reception/dashboard` | | Today's visits, recent check-ins, search. |
| ID verification and photo | check-in flow | | Verify ID and upload a visitor photo; can be required before badge printing. |
| Badge printing | `/reception/badge-printing` | `visitors:print_badge` | Print and reprint a visitor badge with a signed QR. |
| Check-out, re-enter | dashboard, `/badge/scan` | | Check out, or let a visitor back in with the badge. |
| Emergency: who is inside | `/emergency/inside` | `emergency:view` | Live list of people currently inside. |
| Export invitations | dashboard | `invitations:export` | CSV or Excel, filtered by status, dates, and board filters. |

## 5. Admin: organisation set-up

| Feature | Route | Permission |
| --- | --- | --- |
| Admin dashboard (analytics, overview) | `/admin/dashboard` | `invitations:view-all` |
| Organisation configuration (including badge printing and ID-verification switches) | `/admin/organisation-configs` | `companies:manage` |
| Branches | `/admin/branches` | `branches:manage` |
| Departments | `/admin/departments` | `departments:manage` |
| Buildings | `/admin/buildings` | `buildings:manage` |
| Floors | `/admin/floors` | `floors:manage` |
| Host employees (directory sync, enable, disable, role assignment) | `/admin/host-employees` | `employees:manage` |
| Visitor categories | `/admin/visitor-categories` | `visitor-categories:manage` |
| Approval workflows (levels and approvers per category) | `/admin/workflows` | `approval-workflow-rules:manage` |
| Roles and permissions | `/admin/roles` | `roles:manage` |
| Form builder (steps, field groups, fields, reorder, publish) | `/admin/form-builder` | `form-builder:manage` |
| Zones (per category and per invitation) | `/admin/zones` | `zones:view`, `zones:manage` |
| All invitations board | `/admin/invitations` | `invitations:view-all` |
| Calendar | `/admin/calendar` | `invitations:view` |
| Audit trail and downloadable reports | `/admin/audit-trail` | `audit-logs:view` |

## 6. Admin: kiosks and devices

| Feature | Route | Permission | Description |
| --- | --- | --- | --- |
| Kiosks register | `/admin/kiosks` | `kiosks:manage` | Add, edit, delete, activate, hide or unhide company-wide kiosks; filter, sort, paginate. |
| Reception desks | `/admin/reception-desks` | `desks:manage` | Registered devices in `kiosk` operating mode. |
| Security gates | `/admin/security-gates` | `gates:manage` | Registered devices in `security` operating mode. |
| Device approval lifecycle | both pages | | New device is Pending; admin approves, then enables, disables or deletes it. |
| Kiosk location validation | admin settings | | When on, kiosks must be at their expected location. |
| Push device token | automatic | | The browser registers an FCM token for notifications (separate from managed devices). |

## 7. Cross-cutting features

- Role- and permission-based menus and route guards.
- Branch scoping through the `X-Branch-ID` header (kiosks and organisation settings are company-wide).
- Light and dark theme, responsive layout, loading and empty states, toasts.
- Live data refresh on dashboards and boards.
- Zod validation of every API response.
- OpenSpec specs for 35 capabilities in `openspec/specs/`.
