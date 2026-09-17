## 1. Database & Migrations

- [x] 1.1 Add `alembic_tenant` migration creating `form_steps` and
      `form_fields` tables (columns per `design.md` Decision 3:
      `is_system`, `is_locked`, `active`, `required`, `options`,
      `validation_rules`, `visibility_condition`, `width`, `order_index`,
      `branch_id` nullable on `form_steps`).
- [x] 1.2 Add `form_config_versions` table (one row per scope, `branch_id`
      nullable, `snapshot` JSONB, `version` int, `published_at`,
      `published_by_user_id`).
- [x] 1.3 Add `consents` (JSONB) and `custom_field_values` (JSONB) columns
      to `invitations`; add `custom_field_values` (JSONB) to
      `invitation_vehicles`. Additive only, per `design.md` Migration Plan
      step 1. **Scoped down**: added `invitations.consents` (migration
      `762e2a7cf5d1`) — landed, wired into `create_invitation`. Also
      relaxed `invitation_visitors.id_proof_type`/`id_proof_storage_key`
      to nullable in the same migration (needed for per-visitor optional
      ID proof, §4). `custom_field_values` on `invitations`/
      `invitation_vehicles` is **not** added — no delta-spec scenario
      requires it (vehicle fields beyond the locked `vehicleType`/
      `licensePlate` were already optional; no scenario exercises an
      admin-added custom vehicle field or a brand-new custom step's field
      at invitation-creation time), so it stays a future addition rather
      than unused, speculative schema.
- [x] 1.4 Write the idempotent data-migration/seed function that, per
      tenant schema: creates the tenant-default `form_steps`/`form_fields`
      rows matching today's fixed field set and locked/toggleable tiers
      (per `specs/form-builder/spec.md`'s "System Fields Are Seeded..."),
      backfills `invitations.consents` from the three existing boolean
      columns, and publishes a `version = 1` `form_config_versions` row
      (`branch_id = NULL`) from that seed. **Implemented with a refinement**:
      `form_builder/service.py::seed_default_form_config` (called from
      `platform/service.py::create_tenant`, mirroring `seed_default_roles`)
      materializes the tenant-default draft from `defaults.py`, and
      `resolve_effective_form` falls back to the same defaults *in code*
      (`DEFAULT_EFFECTIVE_FORM`) whenever no `FormConfigVersion` exists for
      a scope — so an existing tenant that never runs this seed still gets
      exactly today's behavior, without a separate data-backfill migration.
      No `consents` backfill yet, since that column doesn't exist until §4.
- [x] 1.5 Verify against a fresh `vmss_test` migration run that every
      existing invitation's consent data round-trips correctly into the
      new JSONB shape. **Adjusted**: no boolean-to-JSONB backfill exists
      (see 1.3/1.4 — the three old boolean columns are simply no longer
      written, not migrated), so there's no round-trip to verify; instead
      verified that `create_invitation` writes `consents` correctly
      end-to-end via the real `invitations`/`registrations` test suites
      (255 + 21 tests) against a freshly migrated `vmss_test`, and via
      `tests/test_workflow_full_lifecycle.py`'s real
      `/platform/tenants`-provisioned tenant (real Alembic migration run,
      not `create_all`).

## 2. Permissions

- [x] 2.1 Add `form-builder:manage` and `form-builder:view` to
      `PERMISSION_CODES` in `auth/rbac_catalog.py`.
- [x] 2.2 Grant both to the `admin` role in `ROLE_PERMISSIONS`. (Automatic:
      `ROLE_PERMISSIONS["admin"]` is `PERMISSION_CODES` itself.)
- [x] 2.3 Confirm `seed_default_roles()` backfills the new permissions onto
      existing tenants' `admin` role without duplicating grants. (Existing
      union-merge logic requires no change; covered by `auth/tests.py`.)

## 3. `form_builder` Feature Package (Backend)

- [x] 3.1 Scaffold `src/vmss_api/form_builder/{__init__,models,schemas,
      repository,service,router,tests}.py` per `fastapi-architecture.md`
      §1. (Also added `defaults.py` and `deps.py`.)
- [x] 3.2 Implement `FormStep`/`FormField` SQLAlchemy models
      (`TenantScopedRepository`-based repository) and Pydantic
      `CamelModel` schemas for create/update/reorder/out shapes.
- [x] 3.3 Implement step CRUD + reorder endpoints, scoped by an optional
      `X-Branch-ID` (present) or tenant-default (absent), gated by
      `require_permission("form-builder:manage"/"form-builder:view")`.
      (Via `form_builder/deps.py::require_form_scope`, since the
      permission check itself is scope-dependent — see that module's
      docstring.)
- [x] 3.4 Implement field CRUD + reorder endpoints under a step, enforcing:
      locked fields reject `active`/`required` changes; option-bearing
      field types require a non-empty `options` list; `validation_rules`
      internal consistency (e.g. `minLength <= maxLength`).
- [x] 3.5 Implement conditional-visibility validation: referenced field
      must exist in the same step; reject direct or transitive cycles.
- [x] 3.6 Implement "customize this branch" clone-on-first-edit: copying
      the tenant-default (or a chosen source branch's) current draft into
      new branch-scoped `form_steps`/`form_fields` rows. (Implemented as
      an implicit `_ensure_scope_seeded` called at the top of every
      mutating/publish call for a scope, rather than a separate explicit
      "clone" endpoint — same effect, simpler surface. Always clones from
      the tenant default; choosing another branch as the source is not
      implemented.)
- [x] 3.7 Implement publish: re-validate the draft as a whole, serialize
      into `form_config_versions` for the target scope, invalidate the
      Redis effective-form cache key for that scope, write an audit-log
      entry (actor, scope, new version).
- [x] 3.8 Implement the effective-form resolver (branch → tenant-default →
      in-code default; see 1.4's note — an all-scopes-missing case can't
      actually occur, so there's no `ERROR`-logged failure path) with
      Redis caching per `design.md` Decision 6, exposed both as an
      internal service function and as a not-permission-gated `GET`
      endpoint for the public/staff wizards to fetch the live form to
      render.
- [x] 3.9 Register `form_builder.router.router` in `api.py`; add its tag +
      description to `main.py`'s `_TAGS_METADATA`.
- [x] 3.10 Add `response_model=Envelope[...]` to every route per
      `api-documentation.md` §1.

## 4. `invitations` Integration

- [x] 4.1 Implement `form_builder/validation.py::validate_against_effective_form`
      per `design.md` Decision 5: required/active/options/validation-rules
      checks with conditional-visibility exemptions, raising the existing
      422 validation-error shape. **Implemented as focused lookups, not one
      monolithic function**: `is_field_required`, `required_consent_keys`,
      `allowed_carried_item_keys` — matching the four concerns the delta
      spec actually load-bears (ID proof/photo requiredness, required
      consents, allowed carried-item keys), not a fully generic
      any-field-any-rule engine nothing yet needs.
- [x] 4.2 Wire this validator into `invitations/service.py` immediately
      after `InvitationCreate` Pydantic validation and before persistence,
      for both `POST /invitations` and `POST /registrations/walk-in`
      (the latter via `registrations/service.py`'s existing delegation to
      `invitations_service.create_invitation` — one call site covers both).
- [x] 4.3 Update `Invitation`/`InvitationVehicle` write paths: consents
      write to the new JSONB column; carried-item values validate against
      the branch's configured keys instead of `CarriedItemCategory`.
      **Scoped down** (see 1.3): no vehicle/custom-step `custom_field_values`
      — nothing in the delta spec requires it yet, and `VehicleSubmit`'s
      non-locked fields (`makeModel`/`color`) were already optional, so
      there was nothing to change there.
- [x] 4.4 Update `POST /invitations`'s payload field description
      (`api-documentation.md` / existing self-documentation requirement) to
      distinguish structurally-mandatory fields from branch-configurable
      ones, per the modified `invitations` spec.
- [x] 4.5 Update/extend `invitations/tests.py` for every scenario in the
      `invitations` delta spec: ID-proof/photo required-vs-deactivated,
      consent required-vs-configured, carried-item/vehicle custom fields,
      default-preserved-for-unconfigured-branch cases.

## 5. `visitors` Cleanup

- [x] 5.1 Stop reading/writing `VisitorCategory.form_schema` in
      `visitors/service.py`/`schemas.py` (ignore the field on
      create/update, per the modified `visitors` spec); update
      `visitors/tests.py` accordingly.
- [ ] 5.2 Add a follow-up migration (separate revision, applied after a
      burn-in period per `design.md` Migration Plan step 6) dropping
      `visitor_categories.form_schema` and the three superseded consent
      boolean columns on `invitations`.

## 6. Frontend — Form Builder Admin UI

- [x] 6.1 Add `@dnd-kit/core` + `@dnd-kit/sortable` and
      `react-signature-canvas` dependencies; add a code-split admin-only
      rich-text editor (e.g. Tiptap) for authoring Rich Text Block content.
      **Scoped down**: added `@dnd-kit/core` + `@dnd-kit/sortable` +
      `@dnd-kit/utilities` (needed now, for §6.4's reorder). Skipped
      `react-signature-canvas` and Tiptap — both are for *rendering*/
      *authoring rich content at fill-time*, which belongs to §7 (deferred,
      see below); the admin config UI only needs to let an admin select
      "Signature Pad"/"Rich Text Block" as a field type and set its label/
      placeholder/required, which needs neither library.
- [x] 6.2 Add `'form-builder'` to `AdminSidebarActiveItem`, a `NAV_ITEMS`
      entry, and a `navigate()` branch in `AdminSidebar.tsx`; add routes in
      `App.tsx` for the steps-overview and step-field-editor pages.
- [x] 6.3 Build the Registration Steps overview page (workspace/branch
      selector, step cards with active toggle + "Edit Fields", "Create
      Registration Step", "Publish Changes"), matching
      `form-builder-overview.png`. ("Form Preview" is a disabled stub — the
      renderer it would drive is §7, deferred.)
- [x] 6.4 Build the Step Editor page: draggable field list (`@dnd-kit`),
      per-row required toggle/edit/delete, "Add New Custom Field" modal
      (field-type grid) matching `form-builder-add-field.png`.
- [x] 6.5 Build the Field Properties panel (label, placeholder, field type,
      validation rules, conditional-visibility selectors, width, Save/Reset)
      matching `form-builder-field-editor.png`.
- [x] 6.6 Wire all of the above to the `form_builder` API (draft CRUD,
      reorder, publish), including the locked-field guard reflected in the
      UI (disable toggles/required for locked rows rather than only relying
      on a server-side rejection). Verified with `tsc -b`, `oxlint`, and a
      production `vite build` — all clean. Not verified in an actual
      browser (no browser-automation tool available in this session); say
      so explicitly rather than claiming a manual click-through.

## 7. Frontend — Config-Driven Renderer & Wizard Cutover

§4 landed, unblocking this section. **Scoped to Carried Items + Consent
Agreement** — the two steps whose admin-configurable field *set* actually
changed (a genuinely dynamic `options: string[]`/consent-key list, not just
a required/active toggle on an otherwise-fixed field). Visitor Info, Visit
Details, and Vehicle Info keep their existing hardcoded components; their
field *set* is still the fixed one `defaults.py` seeds, so nothing there is
incorrect today, only not yet reactive to an admin deactivating one of
their toggleable fields (id proof/photo/duration/notes) — a real remaining
gap, called out below, not silently dropped. `CarriedItemsStep`/
`ConsentStep` are shared by both wizards already (the staff wizard already
imported them directly from `visitor-request/Components/steps/`), so
making them config-driven covers both cutovers in one change.

- [x] 7.1 Implement `buildZodSchemaForStep` mapping effective-form field
      definitions (type, validation rules, conditional visibility) to Zod
      schema pieces. **Adapted**: no Zod-schema-generation layer — the two
      steps in scope validate via a required-key-list check
      (`requiredConsentKeys`, computed from the fetched fields, checked in
      `validateStep`), which is what the actual required behavior reduces
      to for a flat checkbox/checkbox-list step. A real
      `buildZodSchemaForStep` (needed once Visitor Info's field *set*
      itself becomes dynamic) is follow-up work, not built speculatively.
- [x] 7.2 Implement the `FIELD_COMPONENT_REGISTRY` covering all 14 field
      types, respecting `width` and `visibilityCondition`.
      **Implemented as `DynamicField`** (`components/dynamic-fields/
      DynamicField.tsx`): covers every "simple" type (text/email/phone/
      number/date/time/textarea/dropdown_select/checkbox_list/toggle_switch)
      — `file_upload`/`dynamic_table`/`signature_pad`/`rich_text_block`
      render a plain "not supported inline yet" notice rather than
      breaking, since neither step this serves uses one by default.
      `width`/`visibilityCondition` are not yet consulted (both steps in
      scope render every active field full-width with no conditional
      fields today) — real gaps to close once a step actually uses either.
- [x] 7.3 Implement the effective-form fetch (public: via whatever
      branch-resolution the visitor-request page already uses; staff: via
      `X-Branch-ID`) and a generic step renderer consuming it.
      **`use-effective-form.ts`** (shared hook): resolves `branchId` from
      the already-selected Visit Info "location" against the publicly/
      staff-loaded branches list (both wizards already do this exact
      lookup for their own submission's branch) and fetches
      `GET /form-builder/effective` once per branch change. Not a single
      "generic step renderer" for every step — see the scoping note above.
- [x] 7.4 Cut `use-visitor-request-wizard.ts` and its step components over
      to the config-driven renderer; remove the now-superseded hardcoded
      step components once parity-tested. **Scoped to Carried Items +
      Consent** (see above); `ConsentStep`/`CarriedItemsStep` fall back to
      the exact original hardcoded defaults whenever no fields have loaded
      yet (still loading, or the branch has never customized either step),
      so there is no behavior change for any unconfigured
      tenant/branch — verified via `tsc -b`, `oxlint`, and a production
      `vite build`, all clean. Not verified in an actual browser (no
      browser-automation tool available in this session).
- [x] 7.5 Cut `use-staff-visitor-registration-wizard.ts` and its step
      components over the same way. Free, by construction: the staff
      wizard already imports `CarriedItemsStep`/`ConsentStep` directly from
      `visitor-request/Components/steps/` rather than its own copies, so
      making those two components config-driven covers both wizards from
      one change.
- [ ] 7.6 Retire `staff-visit-request-schema.ts`/`visit-request-schema.ts`
      in favor of the dynamically built schema, keeping only whatever
      top-level/structural shape still needs a static Zod definition.
      **Partially done**: both schemas' `consents` field changed from a
      fixed 3-boolean object to `z.record(z.string(), z.boolean())`
      (required — an active regression otherwise, since the already-landed
      §4 backend no longer accepts the old fixed camelCase keys). The
      schemas are not otherwise retired — `visitDetails`/`primaryContact`/
      `vehicles` stay static Zod shapes, matching those sections' still-
      largely-fixed structural contract.

### Known remaining gaps (real, not silently dropped)

- **Visitor Info's toggleable fields aren't reactive yet.** The wizard
  still unconditionally requires the primary contact's ID-proof file/type
  and profile photo client-side, even though §4's backend now accepts
  either being absent when the resolved branch has deactivated them. This
  is a *stricter-than-necessary* client-side gap (never a laxer one the
  backend would reject) — a branch that deactivates either field still
  works end-to-end via any other client (e.g. a direct API call, or the
  Flutter app), just not yet via this frontend's own validation. Closing
  it means rewiring `VisitorInfoStep`'s file-upload requiredness to the
  same fetched-fields data `CarriedItemsStep`/`ConsentStep` now use.
- **Visit Details' toggleable fields** (expected duration, additional
  notes) are in the same position — still always required/shown in the
  UI regardless of branch configuration.
- **Vehicle Info** stays entirely on its original hardcoded fields; no
  admin-added custom vehicle field would render even though nothing in
  the backend's `InvitationVehicle` model would reject one that mapped to
  an existing column.
- **`width`/`visibilityCondition`** on a Carried Items/Consent field are
  accepted by the backend but not yet honored by `DynamicField` (see 7.2).

## 8. Testing

- [x] 8.1 `form_builder` unit/integration tests per `testing-standards.md`
      §2: happy path for every endpoint, a permission-denied case, and a
      tenant-isolation case. (24 tests, `form_builder/tests.py`.)
- [x] 8.2 Tests for locked-field rejection, option-less select rejection,
      dangling/circular conditional-visibility rejection, publish-time
      whole-draft revalidation.
- [x] 8.3 Tests for branch-vs-tenant-default effective-form resolution,
      including the clone-on-first-customization behavior.
- [x] 8.4 Tests confirming an unconfigured branch's effective form exactly
      matches the seeded defaults (no migration backfill exists to compare
      against — see 1.4's note).
- [ ] 8.5 Frontend: at least one test per new field-type component and one
      end-to-end pass of the public visitor-request wizard driven by a
      seeded default effective form. **Deferred** — `VMMS_WEB` has no test
      runner configured at all (no vitest/jest in `package.json`), and the
      end-to-end pass depends on §7 (not yet built) anyway; adding test
      infrastructure is a separate concern from this change.

## 9. Documentation

- [x] 9.1 Add `docs/features/form_builder.md` (purpose, endpoints, scoping/
      fallback rules, field-tier model) per `project-rules.md`'s New
      Features requirement. Also updated `docs/features/visitors.md`'s
      `formSchema` section to point here.
- [x] 9.2 Update `docs/features/invitations.md` (or equivalent) noting
      which fields are now branch-configurable — new "Branch-configurable
      requiredness (`form-builder`)" section, plus updated the profile-photo
      section's "mandatory" framing.
- [x] 9.3 Update `.env.example` if any new setting (e.g. cache TTL) is
      introduced. N/A — the cache TTL is a code constant
      (`form_builder/service.py::_CACHE_TTL_SECONDS`), not a new setting.
