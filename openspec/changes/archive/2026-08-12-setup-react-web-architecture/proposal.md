## Why

The project currently has no application code — only `.claude/` rules and `openspec/` planning scaffolding exist. Before any feature work can start, the repo needs the Vite + React + TypeScript project scaffolding and the clean-architecture folder structure (`domain` / `data` / `infrastructure` / `presentation` / `composition-root.ts`) that `.claude/rules/clean-architecture.md` and `.claude/rules/data-api-layer.md` already mandate, so every future feature has a consistent place to land.

## What Changes

- Initialize a Vite + React + TypeScript project (package.json, vite.config.ts, tsconfig, index.html, entry point).
- Add Tailwind CSS v4 with `src/styles/theme.css` (`@theme` tokens) and `src/styles/index.css`.
- Create the required folder skeleton with no business feature inside it:
  - `src/domain/entities/` — placeholder for Zod schemas (empty, with a `.gitkeep` or README note).
  - `src/data/api/` — `api-endpoints.ts` (empty `API_ENDPOINTS` const + `ApiEndpointDefinition` type) and `api-client.ts` (`ApiClient` class with `makeRequest`, `buildQueryString`, no endpoints wired yet).
  - `src/data/repositories/` — placeholder for port interfaces.
  - `src/data/use-cases/` — placeholder for use-case classes.
  - `src/infrastructure/` — placeholder for adapters.
  - `src/presentation/context/app-dependencies-context.tsx` — `AppDependenciesProvider` + `useAppDependencies()`.
  - `src/presentation/pages/` — one placeholder home page + route-level structure convention (`<feature>/`, `<feature>/hooks/`, `<feature>/Components/`).
  - `src/presentation/components/ui/` — placeholder for shared UI.
  - `src/assets/icons.ts` — empty icon barrel.
- Add `composition-root.ts` with a lazy `createApp()` that resolves `ApiClient` from `import.meta.env.VITE_API_BASE_URL` and exposes an (initially minimal) `AppDependencies` interface.
- Add `.env.example` documenting `VITE_API_BASE_URL`.
- Wire a minimal router (base layout + one placeholder route) so the app renders and `AppDependenciesProvider` wraps it.
- No business feature (e.g. login, videos) is implemented in this change — this is the reusable skeleton only.

## Capabilities

### New Capabilities
- `app-shell`: The application bootstrap — project scaffolding, DI composition root, ApiClient contract, and a routed shell that renders a placeholder page wrapped in `AppDependenciesProvider`.

### Modified Capabilities
- None (no existing capabilities to modify).

## Impact

- Affected code: entire repo (currently empty) — creates `package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `src/**`, `.env.example`.
- Dependencies added: `react`, `react-dom`, `react-router` (for the route shell), `zod`, `tailwindcss` (v4) and their Vite/TS tooling.
- No APIs are called yet — `ApiClient`/`API_ENDPOINTS` are scaffolded but have zero registered endpoints until a real feature change adds them.
