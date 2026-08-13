## 1. Project Init

- [x] 1.1 Scaffold Vite + React + TypeScript project at repo root (`package.json`, `vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`/`tsconfig.node.json`, `index.html`, `src/main.tsx`, `src/App.tsx`)
- [x] 1.2 Add `.gitignore` (node_modules, dist, .env, etc.)
- [x] 1.3 Install `react`, `react-dom`, `react-router`, `zod`

## 2. Styling

- [x] 2.1 Install Tailwind CSS v4 and its Vite plugin
- [x] 2.2 Create `src/styles/theme.css` with `@theme` and `--color-*` tokens
- [x] 2.3 Create `src/styles/index.css` importing Tailwind and `theme.css`; import it from `src/main.tsx`

## 3. Domain Layer Skeleton

- [x] 3.1 Create `src/domain/entities/` with a `.gitkeep` (no schemas yet — first feature change adds them)

## 4. Data Layer: API Gateway

- [x] 4.1 Create `src/data/api/api-endpoints.ts`: export `API_ENDPOINTS` as an empty `const` object and `ApiEndpointDefinition` as `(typeof API_ENDPOINTS)[keyof typeof API_ENDPOINTS]`
- [x] 4.2 Create `src/data/api/api-client.ts`: `ApiClient` class — constructor strips trailing slash from `baseUrl`; `buildQueryString` using `URLSearchParams`; `makeRequest<T>({ endpointConfig, body?, queryParams?, parserSchema })` implementing headers, conditional `Authorization: Bearer` from `sessionStorage.getItem("token")` (throwing before `fetch` when `hasToken` is true and no token exists), `fetch`, and `parserSchema.parse(await response.json())`
- [x] 4.3 Manually verify `app-shell` spec's HTTP-client requirements against a temporary local test endpoint (token enforcement, schema validation, base-URL trailing-slash handling), then remove the temporary endpoint/test code before finishing

## 5. Data Layer: Ports & Use Cases Skeleton

- [x] 5.1 Create `src/data/repositories/` with a `.gitkeep` (no ports yet)
- [x] 5.2 Create `src/data/use-cases/` with a `.gitkeep` (no use cases yet)

## 6. Infrastructure Skeleton

- [x] 6.1 Create `src/infrastructure/` with a `.gitkeep` (no adapters yet)

## 7. Composition Root

- [x] 7.1 Create `src/composition-root.ts`: `createApp()` with lazy `??=` getter for `apiClient` reading `import.meta.env.VITE_API_BASE_URL`; export `AppDependencies` interface exposing `apiClient`

## 8. Presentation: DI Context & Router Shell

- [x] 8.1 Create `src/presentation/context/app-dependencies-context.tsx`: `AppDependenciesProvider` (wraps `createApp()` result) and `useAppDependencies()` hook that throws when called outside the provider
- [x] 8.2 Create `src/presentation/pages/home/home.tsx` placeholder page
- [x] 8.3 Create `src/presentation/components/ui/` with a `.gitkeep` (no shared UI yet)
- [x] 8.4 Wire `react-router` in `src/App.tsx`: root layout + single route to the placeholder home page, wrapped in `AppDependenciesProvider`

## 9. Assets

- [x] 9.1 Create `src/assets/icons.ts` as an empty barrel (named re-exports added by future features)

## 10. Environment

- [x] 10.1 Create `.env.example` documenting `VITE_API_BASE_URL=http://localhost:8080/api/v1`

## 11. Verification

- [x] 11.1 Run `npm run dev`; confirm the app boots with no console errors and the placeholder home page renders at `/`
- [x] 11.2 Confirm `useAppDependencies()` inside the home page returns the resolved `apiClient` (e.g. via a temporary `console.log`, removed after checking)
- [x] 11.3 Run `npm run build` / `tsc` to confirm the project type-checks cleanly
