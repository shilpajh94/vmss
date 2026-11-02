## Why

`audit-and-harden-api-and-web` and its follow-ups landed about 30 commits
across VMSS_API and VMMS_WEB on `feature/suggestions-fix`. Before they are
merged and deployed, we need to answer two questions:

- Will anything that works today break on the live servers?
- What does the Flutter app have to change to stay compatible now, and to
  keep working once `PUBLIC_ENDPOINT_HARDENING` is turned on (target
  2026-12-31)?

Reviewing the commits found one real deployment risk: new rate limits that,
behind the Kong ingress, are shared by every client. It also found a deploy
order that matters, and a handful of client-visible behaviour changes the
app team has not been told about.

## What Changes

- **Deployment fix (API):**
  - Set `FORWARDED_ALLOW_IPS` in the Kubernetes manifests and the
    DEV/STAGE `.env` templates, so rate limits count per client instead of
    per ingress pod.
  - Until that is live, the three limits added by the audit (`/files`,
    the email assets and `/form-builder/effective`) are the ones that can
    throttle every user at once.
- **Release checklist:** record the merge preconditions:
  - deploy the API before the web portal;
  - run `scripts/upgrade_all_tenants.py` in a quiet window (the new indexes
    are built non-concurrently);
  - restart the Celery workers;
  - leave `ENFORCE_SECRET_CHECK` and `PUBLIC_ENDPOINT_HARDENING` off;
  - add the four footer `VITE_*` variables to each web variable group.
- **Mobile app migration guide:** a hand-off document for the Flutter
  developer listing every API change the app sees. It is split into "must
  ship before this API reaches production", "must ship before strict mode"
  and "recommended".
- No change to the API's request/response contracts. The behaviour changes
  the guide lists already ship in the merged commits:
  - **BREAKING (for clients):** a `group` registration with no visitors now
    returns 422 (G38).
  - **BREAKING (for clients):** reusing an `Idempotency-Key` with a
    different body returns 422, and a concurrent duplicate returns 409.
  - **BREAKING (for clients):** `includeHidden=true` on `/kiosks` is
    ignored without the `kiosks:view` permission.
  - Validation errors use a new 422 message format plus an `errors` list.

## Capabilities

### New Capabilities
- `release-readiness`: the merge and deploy preconditions for a release
  that spans the API, the web portal and the mobile app, and the client
  migration guide that must exist before strict public-endpoint mode is
  enabled.

### Modified Capabilities
- `rate-limiting`: deployed environments must trust their ingress for the
  client address, so a per-IP limit is never shared by every client behind
  the load balancer.

## Impact

- **VMSS_API:**
  - `CI-CD/k8s.yml` and `CI-CD/Openstack-K8.yml` (secret/env), plus the
    `.env` templates used by the DEV/STAGE pipelines;
  - `.env.example` comment;
  - `docs/features/configuration.md`;
  - a new `docs/release/` checklist and `docs/clients/mobile-app-migration.md`.
- **VMMS_WEB:** none in code. The release checklist references its Azure
  variable groups (`VMSS-WEB`, `VMSS-WEB-STAGE`, `VMSS-WEB-PROD`).
- **Flutter app (separate repo):** the work in the migration guide,
  delivered by the app developer.
- **Ops:**
  - the Azure DevOps variable groups (API and web);
  - a maintenance window for the tenant migrations;
  - the Kong ingress pod CIDR, needed for `FORWARDED_ALLOW_IPS`.
