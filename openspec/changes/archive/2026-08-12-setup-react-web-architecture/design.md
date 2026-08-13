## Context

The repo is currently empty except `.claude/` and `openspec/`. Two checked-in rule files already fix the target shape:
- `.claude/rules/clean-architecture.md` — folder layout, dependency direction (`presentation` → `data` → `domain`, `infrastructure` → `data`/`domain`), composition-root/DI pattern, Tailwind v4 theme tokens, icon barrel.
- `.claude/rules/data-api-layer.md` — `API_ENDPOINTS` shape, `ApiClient.makeRequest` contract, Zod wire schemas, port/adapter/use-case conventions, env var (`VITE_API_BASE_URL`).

This design fixes the remaining choices those rules leave open: which concrete tools to install and how to stand up empty-but-structurally-correct folders with nothing to put in them yet (see proposal.md — Why/What Changes for the decision to ship a skeleton with no business feature).

## Goals / Non-Goals

**Goals:**
- Every folder path named in the two rule files exists and is empty-but-valid (no placeholder business logic).
- The app boots, renders one placeholder route, and DI is provable end-to-end (`composition-root.ts` → `AppDependenciesProvider` → `useAppDependencies()`).
- `ApiClient` and `API_ENDPOINTS` exist as real, testable code (per `app-shell` spec requirements) even though zero endpoints are registered yet.

**Non-Goals:**
- Implementing any business feature (login, videos, etc.) — that is a separate future change per capability.
- Setting up test runners/CI — out of scope unless the user asks separately.
- Choosing a state-management library beyond React context — none of the current rules require one.

## Decisions

- **Router: `react-router` (v7, "framework-agnostic" data mode not required — just `BrowserRouter`/`Routes`).** The rules already describe `presentation/pages/<feature>/` as route screens, implying multi-page navigation from day one. Alternative considered: no router, single static page — rejected because the rules' own folder convention (`pages/`, route components) assumes routing exists, and retrofitting it later would touch every future page.
- **`AppDependencies` exposes only `apiClient` for now.** The rules explicitly allow exposing `apiClient` "for debugging or advanced use cases" when no feature-specific use case exists yet. Once the first real feature change adds a use case, it gets added to this interface then — this change does not invent a placeholder use case just to fill the interface.
- **Empty rule-mandated folders (`domain/entities/`, `data/repositories/`, `data/use-cases/`, `infrastructure/`, `presentation/components/ui/`) get a `.gitkeep`.** Git does not track empty directories; a `.gitkeep` is the minimal way to make the skeleton actually present after checkout without inventing fake content.
- **Tailwind CSS v4 via `@theme` in `src/styles/theme.css`, imported by `src/styles/index.css`.** Matches the rule verbatim; no CSS framework alternative considered since the rule is prescriptive.
- **Zod for the (currently empty) `domain/entities/` schemas.** Already mandated by `data-api-layer.md`; installed now so `ApiClient.makeRequest`'s `parserSchema` parameter type-checks against real Zod types instead of `any`.
- **`ApiClient` and `API_ENDPOINTS` are written as real, working code with zero registered endpoints** (`API_ENDPOINTS = {}` typed as `Record<string, never>` today, replaced by real entries when the first feature change lands) rather than left unwritten. This lets the `app-shell` spec's HTTP-client requirements (token enforcement, schema validation, base-URL resolution) be exercised with a throwaway test endpoint during implementation, instead of being unverifiable until a real feature exists.

## Risks / Trade-offs

- **No real feature exists to prove the wiring under production-like conditions** → Mitigation: verify manually (`npm run dev`, confirm the placeholder route renders, confirm `useAppDependencies()` returns the resolved `apiClient`, confirm calling `makeRequest` against a temporary local test endpoint enforces token/schema rules) before marking tasks done; delete any temporary test endpoint before finishing.
- **Adding `react-router` now, before any second page exists** → Mitigation: it is a small, well-known dependency and the rules already assume multi-page routing; cost of adding later (touching every page) is higher than the cost of adding now.
- **`.gitkeep` placeholders could be mistaken for meaningful files later** → Mitigation: name them exactly `.gitkeep` (well-known convention) and remove each one in the same commit that adds the first real file to that folder.
