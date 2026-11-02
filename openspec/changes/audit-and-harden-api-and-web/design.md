## Context

The shared context, the decisions D1–D15, the risks, the migration order and
the **gap register** (G1–G37) live in
`VMSS_API/openspec/changes/audit-and-harden-api-and-web/design.md`. Read that
first. This file adds only web-specific implementation decisions (D-W*) that
the shared D11–D15 leave open.

Current state worth knowing:
- `AsyncRegion`, `useLoadTracker`, `usePresence`, `Modal`, `PendingButton`
  and `CurrentUserContext` already exist and are widely used. This change
  builds on them rather than replacing them.
- 32 hooks repeat a `sessionStorage.getItem('token')` guard.
- About 13 list hooks re-fetch the current user and their options on every
  10-second poll.
- `react-hooks/exhaustive-deps` is clean, so changing hook dependencies is
  low-risk.
- VMMS_WEB has no Prettier. Never run a formatter across files (gotcha).
- `vite.config.ts` is skip-worktree, so edits there never reach git (gotcha).
  The bundle-budget check therefore lives in a separate script, not in
  `vite.config.ts`.

## Goals / Non-Goals

**Goals:** see the shared design. In addition, every web finding from the
2026-10-20 audits is either fixed here or listed in the gap register.

**Non-Goals:** visual redesign; new pages for features the gap register
defers (G2, G3, G13, G15, G16, G17); and turning on the API's strict
hardening.

## Decisions

### D-W1. Permissions come from `/auth/me`, through one `usePermissions()` hook

`CurrentUserContext` gains `permissions: Set<string>`, built as the union of
`branchRoles[].permissionCodes`, and `can(code, branchId?)`.

- **Admin area entry:** allowed if the user holds any of the `*:manage`
  codes the admin pages require. Each page's required code sits next to its
  route definition in `App.tsx`, in a `requires` field.
- **Landing page:** `landingPathFor` still uses role names, because the spec
  defines landing by role.
- **Fallback:** if the API half hasn't shipped and `permissionCodes` is
  missing, `can()` falls back to the current role-name checks. This keeps the
  web shippable on its own; remove the fallback in §8.

### D-W2. The HTTP client sends the token whenever one exists

`hasToken: false` endpoints keep meaning "a token is not *required*", but
the client now attaches `Authorization` whenever a session token is present.
That one change in `api-client.ts` fixes every master-data list at once,
with no per-endpoint edits. A 401 on an endpoint that doesn't require a
token clears the token but does not redirect. The API treats an invalid
token as anonymous on these routes anyway.

### D-W3. Route guards live in the layouts

`AdminLayout` and `StaffLayout` each:
1. check the token;
2. await the current user (from context);
3. enforce the route's `requires` permission;
4. render `<Outlet/>` only once that passes. Until then they render the
   layout skeleton.

Then:
- The 32 per-hook token checks are deleted.
- Login pages redirect an already-signed-in user to their landing page.
- The return path is captured as `?from=` (same-origin path only, validated
  with `new URL(from, location.origin).origin === location.origin`).

Because the session lives in `sessionStorage`, a new tab still starts signed
out (gap G1 covers refresh tokens). `from=` at least brings the user back to
the deep link after signing in again.

### D-W4. `useLiveResource` contract

```
useLiveResource({ load, reference?, pollMs = 10_000 })
  → { data, reference, isInitialLoading, error, hasFailed, retry, refresh }
```

- `reference` loaders run once per mount and on a manual `refresh()`, never
  on a poll.
- A failed poll sets `hasFailed` and does not toast. `usePageRefresh` shows
  the retrying state.
- It wraps the existing `useLoadTracker` (out-of-order protection) and
  `usePolling`.

List hooks move to it one at a time. Each move is behaviour-preserving
apart from the dropped repeat toasts and fetches. Copy
`use-admin-audit-trail.ts:58` and `use-live-dashboard.ts:91`, which already
behave this way.

### D-W5. Error-message extraction

`toUserMessage(error, fallback)` lives in `presentation/utils/`:
- it reads the envelope's `message`, and the first field error if present,
  from `ApiError`;
- it falls back to `fallback` for network errors, 5xx responses, or an empty
  message.

It is used in every form hook's catch block, replacing the hard-coded
"Something went wrong". The kiosk form already does this, so it is the
reference implementation.

### D-W6. Unsaved-changes guard

`useUnsavedChangesGuard(isDirty)` combines react-router's `useBlocker` with
a `beforeunload` listener, and shows the existing `ConfirmDialog`.
`isDirty` compares against the last-saved snapshot. It does not compare
against the initial render, which avoids the QA F13 nit where input typed
during loading counts as saved. The form-builder panel uses the same hook
when switching between fields.

### D-W7. Employee create

`host-employee-repository.ts` `create` calls `POST /auth/employees`, with
`departmentId` required (the spec already makes Department required).
`update` keeps its current endpoint. The sync-based create path is deleted
entirely, and a unit test asserts that `/auth/employees/sync` is never
called by create.

### D-W8. Timezone list

The list is built from `Intl.supportedValuesOf('timeZone')`, with labels
from `Intl.DateTimeFormat(..., { timeZoneName: 'shortOffset' })`. A legacy
`GMT±HH:MM` value is matched to the first zone with the same current
offset, preferring a curated list (`Asia/Kolkata`, `Asia/Dubai`,
`Europe/London`, …) so `+05:30` maps to `Asia/Kolkata`.

### D-W9. Option lists past 100 entries

`fetchAllPages(fetchPage, { pageSize: 100, max: 2000 })` lives in
`data/api/`. Pickers pass `status: 'active'` and `isActive` filters. A
stored inactive value is shown through a one-off get-by-id label lookup,
not by listing inactive items.

### D-W10. Bundle budget check

`scripts/check-bundle-budget.mjs` reads the build manifest. It walks the
`index.html` entry and its static imports, gzips each file, and fails
above 350 KB. It runs as `npm run build:check`. The before and after
numbers are recorded in `tasks.md` §0 and §5.

### D-W11. Contrast tokens

The changes are limited to:
- `--color-text-faint` in light mode, to `#64748b` (slate-500, 4.76:1 on
  white);
- the dark-mode value, to `#94a3b8` (about 6.9:1 on `#0f172a`);
- a new `--color-success-text`: `#047857` in light mode, `#34d399` in dark.

The values are confirmed with a contrast check during apply. Before and
after screenshots of a list page, the board and a dashboard go to the user
before merge (shared D14).

## Risks / Trade-offs

- **[Risk] Moving the guard into the layouts changes the redirect timing.**
  A page could briefly render without a user. → The layout renders only its
  skeleton until the guard resolves. Run the e2e journeys for every role.
- **[Risk] The D-W1 fallback hides a missing API field.** → Log a console
  warning once when `permissionCodes` is absent; §8 removes the fallback.
- **[Risk] Lazy chunks fail to load after a deploy (stale `index.html`).**
  → Wrap `React.lazy` in a single reload-on-chunk-error retry.
- **[Trade-off]** Removing the stubs (Import Hosts, logo picker, Filters,
  Track via Email) takes away UI the client has seen before. This is
  accepted because each one did nothing; each is listed in the gap register
  for when the real feature is built.

## Migration Plan

1. §1–§2 (P0 bugs and contract) can ship before the API half, except the
   items marked "needs API §4".
2. §3 onwards ships after the API half's §4 is deployed.
3. There is no data migration. A legacy timezone or purpose slug is upgraded
   lazily on the next save.
4. Rollback is per section (one commit each).
