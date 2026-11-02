# Release checklist: audit and harden (October 2026)

Covers branch `feature/suggestions-fix`:
- VMSS_API `f7ba135..` (the `audit-and-harden-api-and-web` work, G38 and
  the move-only refactors);
- VMMS_WEB `bd887e2..`.

The detail behind each line is in
`openspec/changes/release-readiness-and-mobile-app-alignment/design.md`.
The app-facing changes are in `docs/clients/mobile-app-migration.md`.

## 1. Before merging

- [ ] **Ingress range.** Get the ingress pod CIDR for each environment from
  ops (Kong in PROD). Add it as the `FORWARDED_ALLOW_IPS` variable in that
  environment's API variable library.
  - The k8s secret (`CI-CD/k8s.yml`, `CI-CD/Openstack-K8.yml`) passes it to
    the pods.
  - Until it is set, no proxy is trusted (today's behaviour). Every client
    behind the ingress then shares one bucket for the per-IP rate limits,
    including the limits this release adds: signed file URLs 300/min, email
    assets 600/min, `/form-builder/effective` 120/min.
  - If the CIDR isn't known: use `*` together with a NetworkPolicy that
    admits API traffic from the ingress only.
- [ ] **Mobile app.** The app developer has confirmed every item in section
  A of the mobile migration guide (or marked it "not used") for the app
  version users will run against this API.
- [ ] **Web footer links.** Add `VITE_SUPPORT_EMAIL`, `VITE_PRIVACY_URL`,
  `VITE_TERMS_URL` and `VITE_SECURITY_URL` (https URLs and an address) to
  the web variable groups `VMSS-WEB`, `VMSS-WEB-STAGE` and `VMSS-WEB-PROD`.
  - They are optional: a link stays hidden until its value is set.
  - They are baked in at build time, so a new web build is needed after
    adding them.

## 2. What changes on merge

**No behaviour change.**
- **Refactors:** the five move-only commits. The whole suite passes on each
  commit.
- **Additive response fields:**
  - `/auth/me` `branchRoles[].permissionCodes`;
  - invitation list items `preferredVisitDate`, `preferredVisitTime` and
    `currentApprovalStep`;
  - invitation detail `checkInDevice`/`checkOutDevice`.
- **Optional query parameters:** notifications `sortBy`/`sortOrder`.
- **Flags that stay off:**
  - `PUBLIC_ENDPOINT_HARDENING=false`: legacy anonymous calls only gain
    `Deprecation: true` and `Link` headers.
  - `ENFORCE_SECRET_CHECK=false`: a weak `JWT_SECRET_KEY` only logs a
    startup warning.
- **Dockerfile:** unchanged, so `APP_ENV` still comes from each
  environment's `.env`.

**Visible to clients as soon as the API is deployed:**

| Endpoint | Change |
|---|---|
| Group registration with no visitors (`POST /invitations`, `POST /registrations/walk-in`) | 422 "A group registration must list at least one visitor" |
| Routes taking `Idempotency-Key` | it replays only for the same route, caller and body; another body gives 422, and a concurrent duplicate gives 409 |
| `GET /kiosks?includeHidden=true` | hidden kiosks only for callers with `kiosks:view` |
| 422 from multipart creates | `message` is `Invalid request: …` and `errors[{field, message}]` is added; input values are no longer echoed |
| Multipart requests | 413 above 160 MiB or 100 files |
| `/files`, email assets, `/form-builder/effective` | new per-client rate limits (see section 1) |

The web portal in this release already handles all of these.

## 3. Deploy order (DEV, then STAGE, then PROD)

1. **API image.** Deploy the API.
2. **Tenant migrations.** Run `scripts/upgrade_all_tenants.py` against the
   environment, then check every tenant reports head `14319832f01f`.
   - The two migrations build indexes **without** `CONCURRENTLY`, so
     writes to `invitations` and `audit_logs` wait while each index builds.
   - In PROD, check the sizes first
     (`SELECT count(*) FROM <schema>.invitations;` and the same for
     `audit_logs`), then run it in a low-traffic window.
   - The code doesn't depend on the indexes, so traffic before they exist
     is correct, only slower on search and audit filters.
   - If the database role can't create `pg_trgm`, the trigram indexes are
     skipped with a log line rather than failing the migration.
3. **Celery.** Restart the workers and beat, so the new task code is
   loaded. Task names and arguments are unchanged, so queued messages
   still run.
4. **Web image.** Deploy the web portal only after step 1. The board reads
   the approval step and visit date and time from the invitation list; on
   the old API, reception loses Approve and Delegate on the board.
5. **Smoke test.** Run `scripts/qa_regression/run.py` and the web e2e
   smoke against the environment (DEV/STAGE). In PROD, watch for 429s on
   `/files` and `/form-builder/effective` for the first hour.

## 4. Rollback

- Roll the web and API back **together**. The new web relies on the new
  list-item fields.
- Rolling back the web alone is always safe.
- No database downgrade is needed: the migrations only add indexes.

## 5. Later: strict public-endpoint mode

Enable `PUBLIC_ENDPOINT_HARDENING` first in STAGE, then in PROD. Do it
only after an app release covering section B of the mobile migration
guide has reached its users, and once no `Deprecation: true` responses
remain in the logs. The target is 2026-12-31.

## 6. Known gaps left as they are

- **`VITE_SSO_TENANT_SLUG`.** The web pipelines pass it as a build
  argument, but neither web Dockerfile declares it, so builds use the
  code's default.
  - Declaring it now would break SSO sign-in in any environment whose
    variable group lacks it.
  - Add it to all three groups first, then declare it in both
    Dockerfiles.
- **`docs/features/configuration.md`** is marked skip-worktree in this
  repo, so edits to it don't reach git. The deployment guidance for
  `FORWARDED_ALLOW_IPS`, `ENFORCE_SECRET_CHECK` and the body caps lives in
  this checklist until that flag is cleared.
