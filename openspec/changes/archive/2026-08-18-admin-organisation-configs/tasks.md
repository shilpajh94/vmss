## 1. Theme

- [x] 1.1 Add `--color-admin-accent: #0b8b84` to `src/styles/theme.css` `@theme` block

## 2. Domain schema

- [x] 2.1 Add `src/domain/entities/organisation-config-schema.ts` with `OrganisationConfigSchema` (organisation name, logo URL/ref, default timezone, auto-approve boolean, pass badge expiry duration) and its `z.infer` type

## 3. API endpoints

- [x] 3.1 Add `GET_ORGANISATION_CONFIG` (`GET /organisation-config`, `hasToken: true`), `UPDATE_ORGANISATION_CONFIG` (`PUT /organisation-config`, `hasToken: true`), and `UPLOAD_ORGANISATION_LOGO` (`POST /uploads/organisation-logo`, `hasToken: true`) to `src/data/api/api-endpoints.ts`

## 4. Repository port, adapter, use cases

- [x] 4.1 Add `src/data/repositories/organisation-config-repository.ts` with `OrganisationConfigRepository` interface: `get(): Promise<OrganisationConfig>`, `update(config: OrganisationConfig): Promise<OrganisationConfig>`, `uploadLogo(file: File): Promise<UploadResponse>`
- [x] 4.2 Add `src/infrastructure/organisation-config-repository.ts` implementing `OrganisationConfigRepository` via `ApiClient.makeRequest`/`uploadFile` against the new endpoints and schemas
- [x] 4.3 Add `src/data/use-cases/get-organisation-config.ts` (`GetOrganisationConfigUseCase`)
- [x] 4.4 Add `src/data/use-cases/update-organisation-config.ts` (`UpdateOrganisationConfigUseCase`)
- [x] 4.5 Add `src/data/use-cases/upload-organisation-logo.ts` (`UploadOrganisationLogoUseCase`)

## 5. Composition root

- [x] 5.1 Wire `resolveOrganisationConfigRepository`, `resolveGetOrganisationConfigUseCase`, `resolveUpdateOrganisationConfigUseCase`, `resolveUploadOrganisationLogoUseCase` in `src/composition-root.ts` and expose the three use cases on `AppDependencies`

## 6. Shared UI

- [x] 6.1 Add `src/presentation/components/ui/ToggleSwitch.tsx` (`{ checked, onChange, label }`, styled per the Figma switch)
- [x] 6.2 Add admin sidebar icons (home, settings, git-branch, building, layers, monitor, user-check, tag, bell) to `src/presentation/components/icons.tsx`, reusing existing `UsersIcon`/`ShieldIcon`/`SearchGlyphIcon`/`SlidersIcon` where the glyph already matches
- [x] 6.3 Add `src/presentation/components/AdminSidebar.tsx`: brand mark, the ten nav items (Dashboard, Organisation Configs, Branches, Departments, Buildings, Floors, Reception Desks, Security Gates, Host Employees, Visitor Categories), an `activeItem` prop, and a footer version indicator; only "Organisation Configs" navigates (to `/admin/organisation-configs`), the rest are inert buttons

## 7. Page: hook and data flow

- [x] 7.1 Add `src/presentation/pages/admin-organisation-configs/hooks/use-admin-organisation-configs.ts`: checks `sessionStorage` token on mount (redirect to `/staff/login` if missing), loads current staff user + organisation config, tracks last-loaded/saved config vs. in-progress edited form state, exposes field setters, `save`, `cancel`, `retry`, loading/error state, and fires toasts on load failure, save success, and save failure
- [x] 7.2 Wire the file upload flow: `FileUploadField`'s `onUpload` calls `uploadOrganisationLogoUseCase.execute(file)` and stores the returned `fileRef` in the edited (unsaved) form state, applied only on "Save Configs"

## 8. Page: components and layout

- [x] 8.1 Add `src/presentation/pages/admin-organisation-configs/Components/TopBar.tsx`: breadcrumb title + description, workspace search field (inert), notification indicator (inert), signed-in admin name/role
- [x] 8.2 Add `src/presentation/pages/admin-organisation-configs/Components/GeneralInformationCard.tsx`: organisation name (`TextField`), logo upload (`FileUploadField`), default timezone (`SelectField`, hardcoded options)
- [x] 8.3 Add `src/presentation/pages/admin-organisation-configs/Components/VisitorPolicyCard.tsx`: auto-approve toggle (`ToggleSwitch`), pass badge expiry duration (`SelectField`, hardcoded options)
- [x] 8.4 Add `src/presentation/pages/admin-organisation-configs/admin-organisation-configs.tsx`: renders `AdminSidebar`, `TopBar`, content header with "Filters" affordance (inert), the two cards, and the "Cancel Changes"/"Save Configs" footer actions; shows `LoadingState` while loading and an inline error-with-retry state on load failure, matching the Staff dashboard's pattern

## 9. Routing

- [x] 9.1 Add the `/admin/organisation-configs` route to `src/App.tsx` rendering the new page

## 10. Verification

- [x] 10.1 Run the dev server and visually compare `/admin/organisation-configs` against the Figma design (node `203:8`) for layout, spacing, and color fidelity
- [x] 10.2 Manually verify: auth redirect, inert nav items, load/error/retry, logo upload validation (type/size), field edits, Cancel Changes reverting edits, Save Configs success and failure toasts
- [x] 10.3 Run lint/type-check and any existing test suite
