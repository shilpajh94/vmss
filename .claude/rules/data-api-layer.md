---
description: HTTP API client, endpoints registry, Zod validation, ports/adapters, use cases, and UI wiring for API features
globs:
  - src/data/**/*
  - src/infrastructure/**/*
  - src/domain/**/*
  - src/composition-root.ts
alwaysApply: false
---

# Data layer & HTTP API

Apply this rule when adding or changing **REST-style calls**, **`ApiClient`**, **endpoints**, **repository ports/adapters**, **use cases** that hit the network, or **composition-root** wiring for those dependencies.

**Dependency reminder:** `data/` never imports `infrastructure/` or `presentation/`. `infrastructure/` may import `data/` (ApiClient, `API_ENDPOINTS`, port interfaces) and `domain/` (schemas). Presentation never calls `ApiClient` or infrastructure directly—only **use cases** via **`useAppDependencies()`**.

---

## `src/data/api/api-endpoints.ts`

- Export **`API_ENDPOINTS`** as a **`const` object**; keys are **UPPER_SNAKE** scenario names (e.g. `LOGIN`).
- Each entry: **`endpoint`** (`string`, path starting with **`/`**), **`method`** (`GET` | `POST` | `PUT` | `PATCH` | `DELETE`), **`hasToken`** (`boolean`).
- **`hasToken: true`**: `ApiClient` adds **`Authorization: Bearer …`** from **`sessionStorage.getItem("token")`**; if missing, throw before `fetch`.
- Export **`ApiEndpointDefinition`** as **`(typeof API_ENDPOINTS)[keyof typeof API_ENDPOINTS]`** so `makeRequest` accepts any registered route.

---

## `src/data/api/api-client.ts`

- **`ApiClient`** constructor: **`baseUrl`** with trailing slash stripped.
- **`makeRequest<T>({ endpointConfig, body?, queryParams?, parserSchema })`** → **`Promise<T>`**:
  - Build URL: **`baseUrl + endpointConfig.endpoint`** + optional query string.
  - **`buildQueryString`**: prefer **`URLSearchParams`** (correct **`?`**, encoding); avoid hand-rolled concatenation bugs.
  - Headers: **`Content-Type: application/json`**; conditional **`Authorization`** per `hasToken`.
  - **`fetch`**: `method` from config; **`body`**: use **`JSON.stringify(body)`** only when the request should send a JSON body (pass **`undefined`** for GET / no body so the client does not send a bogus body).
  - Response: **`parserSchema.parse(await response.json())`** — every success path returns **validated** data; invalid JSON shape → **`ZodError`**.
- Do not scatter **`fetch`** elsewhere in `data/`; all HTTP goes through **`ApiClient`**.

---

## `src/domain/entities/*-schema.ts` (wire contracts)

- **`export const XxxSchema = z.object({ … })`** — property names match **real JSON** (snake_case if the API uses it).
- **`export type Xxx = z.infer<typeof XxxSchema>`** — **one** source of truth; no duplicate interface for the same payload.
- **`import z from "zod"`** (default import), consistent with the repo.

---

## `src/data/repositories/*.ts` (ports)

- **`interface`** only: methods return **`Promise<…>`** with types from **`domain`** schemas.
- No **`fetch`**, no **`ApiClient`**, no React.

---

## `src/infrastructure/*.ts` (adapters)

- **`implements`** the matching port from **`data/repositories/`**.
- Constructor takes **`ApiClient`** (readonly).
- Each backend operation: **`this.apiClient.makeRequest<T>({ endpointConfig: API_ENDPOINTS.KEY, body?, queryParams?, parserSchema: XxxSchema })`**.

---

## `src/data/use-cases/*.ts`

- Class + constructor-injected port(s).
- **`execute`** (or named methods) delegates to the port only; return types from **domain** inferred types.

---

## `src/composition-root.ts` (wiring for API-backed features)

- Read **`import.meta.env.VITE_API_BASE_URL`** (no trailing slash); pass to **`new ApiClient(baseUrl)`**.
- Lazy chain: **`resolveApiClient`** → **`resolve<Feature>Repository`** (adapter) → **`resolve<Feature>UseCase`**.
- Expose new use cases on **`AppDependencies`** for the UI.

---

## Environment

- **`.env.*`**: **`VITE_API_BASE_URL`** = API origin + prefix (e.g. `http://localhost:8080/api/v1`). Vite exposes only **`VITE_*`** to client code.

---

## End-to-end checklist (new API or new project)

1. **Env** — set **`VITE_API_BASE_URL`**; composition root passes it to **`ApiClient`**.
2. **Endpoint** — add entry to **`API_ENDPOINTS`** in **`api-endpoints.ts`**.
3. **Schema** — add Zod schema + **`z.infer`** type under **`src/domain/entities/`**.
4. **Port** — extend or add **`interface`** in **`src/data/repositories/`**.
5. **Adapter** — implement port in **`src/infrastructure/`** using **`makeRequest`** + schema.
6. **Use case** — add class under **`src/data/use-cases/`** calling the port.
7. **Composition root** — wire **`ApiClient` → adapter → use case`**; add to **`AppDependencies`**.
8. **Hook** — **`useAppDependencies()`** → use case; **`useCallback`** + **`await execute(...)`**; complete dependency arrays (**`loginUseCase`**, **`navigate`**, etc.).
9. **Form / UI** — **`onSubmit`** handler calls **`e.preventDefault()`** first so credentials are not sent as URL query params.

---

## One-line flow

**`API_ENDPOINTS` + `makeRequest` + Zod** → **infrastructure repository** → **use case** → **`createApp`** → **`useAppDependencies` in hook** → **component**.
