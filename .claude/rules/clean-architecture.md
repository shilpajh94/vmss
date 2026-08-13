---
description: Layered architecture, DI, presentation boundaries (matches this repo)
alwaysApply: true
---

# Architecture (React + Vite + TS)

**Dependency direction points inward:**

`presentation` → `data` → `domain`  
`infrastructure` → `data` / `domain`  

Only **`src/composition-root.ts`** wires concrete implementations (ApiClient, repositories, use cases) and exposes **`AppDependencies`** to React.

There is **no** `src/application/` folder in this project. The **application boundary** (use cases + repository ports) lives under **`src/data/`**.

---

## Folder structure (required)

| Path | Role |
|------|------|
| **`src/domain/`** | Shared contracts: Zod schemas for API payloads/responses and **`z.infer<typeof Schema>`** types. No React. (Zod is allowed here as the runtime shape checker for wire data.) |
| **`src/data/api/`** | HTTP gateway and route registry — see **`.cursor/rules/data-api-layer.mdc`**. |
| **`src/data/repositories/`** | **Ports**: TypeScript **`interface`** files (e.g. `AuthRepository`). Define what use cases need from the outside; no `fetch`, no React. |
| **`src/data/use-cases/`** | **Use case classes**: constructor-injected port(s), **`execute(...)`** (or feature-named methods) orchestrate one scenario. |
| **`src/infrastructure/`** | **Adapters**: classes that **`implement`** `data/repositories` ports, call **`ApiClient`**, pass **`API_ENDPOINTS.*`** and domain **Zod** schemas into `makeRequest`. (In this repo, adapters live directly under `src/infrastructure/*.ts`.) |
| **`src/presentation/`** | React: components, **`presentation/context/app-dependencies-context.tsx`**, route-level **`hooks/`** next to features (e.g. login). |
| **`src/composition-root.ts`** | Lazy `createApp()`: resolves `ApiClient` → repository adapter → use case; reads **`import.meta.env.VITE_API_BASE_URL`**. |

---

## Dependency rules (enforce)

- **`domain/`** must not import from `data/`, `infrastructure/`, or `presentation/`.
- **`data/`** must not import from `infrastructure/` or `presentation/`.
- **`presentation/`** must not import from `infrastructure/` (use **`useAppDependencies()`** → use cases only).
- **`infrastructure/`** may import **`data/`** (ApiClient, endpoints, port types) and **`domain/`** (schemas/types).

Cross-feature sharing: **`domain/`** types/schemas, **`data/`** ports/use cases, or shared presentation UI — not by importing infrastructure from the UI.

---

## Ports & use cases (required pattern)

- **Ports**: `interface` in **`src/data/repositories/<name>.ts`** (e.g. `AuthRepository`).
- **Use case**: class in **`src/data/use-cases/`**, takes port(s) in the **constructor**; methods return **`Promise<...>`** with types from **`z.infer`** / domain schema exports.
- **Adapter**: class in **`src/infrastructure/`** (e.g. `src/infrastructure/*-repository.ts`), **`implements`** the port, receives **`ApiClient`** (and any other adapters) via constructor.

---

## Composition root & DI (required pattern)

- **`createApp()`** in **`composition-root.ts`**: lazy getters (`??=` resolvers) for `apiClient`, repositories, use cases — **no eager construction** of the whole graph.
- **`AppDependencies`** interface lists what the UI may use (e.g. `loginUseCase`, and optionally `apiClient` / `authRepository` for debugging or advanced cases).
- **`AppDependenciesProvider`** + **`useAppDependencies()`** in **`presentation/context/app-dependencies-context.tsx`** — the only way presentation gets use cases; **no** global singletons for repos/use cases.

---

## Styling (required)

- **Tailwind CSS v4** only (no Bootstrap or other CSS frameworks).
- Theme tokens: **`@theme`** in **`src/styles/theme.css`** with **`--color-*`** custom properties (pulled in via **`src/styles/index.css`**).

---

## Asset icons (required pattern)

- Barrel: **`src/assets/icons.ts`** — re-export SVGs with named exports.
- Components import icons **only** from **`assets/icons`**, never deep-import from **`src/assets/`** except inside the barrel.

---

## HTTP / API / Zod / `makeRequest` (detail)

All **endpoint registry**, **`ApiClient`**, **Zod response schemas**, **repository adapters**, **use-case → hook** steps, and **env (`VITE_API_BASE_URL`)** live in:

**`.cursor/rules/data-api-layer.mdc`** (`alwaysApply: false`, scoped by globs to `src/data/**`, `src/infrastructure/**`, `src/domain/**`, `composition-root.ts`).

---

## React layer guidance

- **Pages**: route screens live under **`src/presentation/pages/<feature>/`** (e.g. `login-page/`, `videos-page/`), with the route component typically at `src/presentation/pages/<feature>/<feature>.tsx`.
- **Feature hooks**: page-specific orchestration hooks live next to the page under **`src/presentation/pages/<feature>/hooks/`** (e.g. `use-login-page.ts`, `use-videos-page.tsx`).
- **Feature components**: page-specific UI pieces live under **`src/presentation/pages/<feature>/Components/`** and should not be imported cross-feature unless they are promoted to shared UI.
- **Shared components**: reusable UI lives under **`src/presentation/components/`** (including `src/presentation/components/ui/`).
- **UI state** (inputs, errors, loading) stays in page components or feature hooks (typically under **`src/presentation/pages/<feature>/hooks/`**).
- **Side effects** that talk to the backend only through **use cases** from context — never **`fetch`** in presentation.
- Short docblocks at module boundaries where non-obvious (composition root, context, ports).
