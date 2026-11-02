## 1. Trusted ingress for rate limits (API config, design D2)

- [ ] 1.1 Get the ingress pod CIDR for DEV, STAGE and PROD from ops (Kong in PROD).
- [x] 1.2 *(Added to the `$(proj_branch)-secret` in both manifests. The deployments read it through `envFrom`, so it overrides the image's `.env` and the committed `.env` template needs no change. An unresolved `$(FORWARDED_ALLOW_IPS)` trusts no proxy, which is today's behaviour; verified against uvicorn's parser.)* Add `FORWARDED_ALLOW_IPS: "$(FORWARDED_ALLOW_IPS)"` to the app secret in `CI-CD/k8s.yml` and `CI-CD/Openstack-K8.yml`. Confirm the `.env` template the DEV/STAGE pipelines token-replace carries `FORWARDED_ALLOW_IPS=__FORWARDED_ALLOW_IPS__`.
- [x] 1.3 *(The `.env.example` comment is updated. `docs/features/configuration.md` is skip-worktree in this repo, so its edit can't reach git; the full guidance is in `docs/release/2026-10-audit-and-harden.md`, which records that gap.)* Document the setting under "Network and request limits" in `docs/features/configuration.md`: what to set behind Kong, and the `*` plus NetworkPolicy fallback. Update the `.env.example` comment to match.
- [ ] 1.4 Verify on DEV after deploy. Two clients on different networks hitting `GET /form-builder/effective` 130 times between them in a minute both get 200s. A single client sending 130 gets 429 on its own.

## 2. Release checklist (design D1, D3, D4)

- [x] 2.1 Write `docs/release/2026-10-audit-and-harden.md`, covering:
  - the merge verdict table from design D1;
  - the deploy order (API, then the tenant upgrade, then the worker restart, then the web);
  - the rollback rule (roll the web and API back together);
  - the flags that stay off;
  - the four web `VITE_*` footer variables per variable group (`VMSS-WEB`, `VMSS-WEB-STAGE`, `VMSS-WEB-PROD`);
  - the `VITE_SSO_TENANT_SLUG` Dockerfile gap, left as is on purpose.
- [x] 2.2 *(In the checklist's step 3.2.)* Add a step to the checklist: check the production table sizes (`invitations`, `audit_logs`) and pick the migration window before running `scripts/upgrade_all_tenants.py`.
- [x] 2.3 *(Linked from `docs/qa/2026-10-full-stack-qa.md` under "Releasing". `configuration.md` is skip-worktree, see 1.3.)* Link the checklist from `docs/qa/2026-10-full-stack-qa.md` and `docs/features/configuration.md`.

## 3. Mobile app migration guide (design D5)

- [x] 3.1 *(Also published as a shareable page with a per-viewer checklist: https://claude.ai/artifact/4WQ1ydDjJ766DnSrLaqhye)* Write `docs/clients/mobile-app-migration.md` for the app developer:
  - sections A (before this API reaches production), B (before strict mode, target 2026-12-31) and C (recommended);
  - every item gives the endpoint, before and after behaviour, what the app must do, and an example request or response.
- [x] 3.2 Add the error-format appendix:
  - the new 422 body (`message` plus `errors[{field, message}]`);
  - the idempotency 409 and 422 bodies;
  - 413;
  - the 429 envelope;
  - the `Deprecation`/`Link` headers.
- [ ] 3.3 Hand the guide to the app developer. Record their answer for each A item ("done in vX.Y" or "not used by the app").

## 4. Flutter app: must ship before this API reaches production

*(Owned by the app developer in the Flutter repo; handed over through `docs/clients/mobile-app-migration.md` on 2026-10-26. These are not implemented in VMSS_API or VMMS_WEB.)*

- [ ] 4.1 A1: block a group registration with no co-visitors in the app, and show the API's 422 message if it still happens.
- [ ] 4.2 A2: idempotency:
  - one UUID per user action, reused only to retry the identical request;
  - never reused for another endpoint or body;
  - on 409, back off and retry with the same key;
  - on an idempotency 422, use a new key.
- [ ] 4.3 A3: parse 422 `errors[]` for field errors and fall back to `message`; remove any parsing of pydantic's raw error text.
- [ ] 4.4 A4: handle 413 (file too large or too many files) and 429 (show "please wait", back off, never retry at once).
- [ ] 4.5 A5 (if used): call `GET /kiosks?includeHidden=true` with a staff token holding `kiosks:view`.

## 5. Flutter app: must ship before strict mode is enabled

*(Owned by the app developer, as section 4.)*

- [ ] 5.1 B1: send the approved `device-id` header on every tracking-ID check-in from a device; staff flows send the bearer token.
- [ ] 5.2 B2: tracking by email runs OTP request, then verify, then `GET /invitations/track?email=` with `Authorization: Bearer <proofToken>`.
- [ ] 5.3 B3: send `X-Device-Key` on `GET /hosts/search` and the other visit-info lookups from the kiosk.
- [ ] 5.4 B4 (if used): call `GET /auth/employees` with the staff token, or switch the kiosk host picker to `GET /auth/employees/directory`.
- [ ] 5.5 B5 (if used): call `/kiosks` with a staff token holding `kiosks:view`.
- [ ] 5.6 B6: log responses carrying `Deprecation: true` in debug and test builds, and confirm a full test pass shows none.

## 6. Flutter app: recommended

*(Owned by the app developer, as section 4.)*

- [ ] 6.1 C1: gate staff features on `/auth/me` `branchRoles[].permissionCodes`, not role names.
- [ ] 6.2 C2: read `currentApprovalStep`, `preferredVisitDate` and `preferredVisitTime` from invitation list items; drop the per-item detail fetch.
- [ ] 6.3 C3: show `checkInDevice`/`checkOutDevice` on the visit detail.
- [ ] 6.4 C4: submit the purpose of visit as its label; show legacy slugs as labels.
- [ ] 6.5 C5: treat the company `defaultTimezone` as an IANA zone and tolerate legacy `GMT±HH:MM`.
- [ ] 6.6 C6: cache `GET /form-builder/effective` per branch for the session.
- [ ] 6.7 C7: map tracking statuses `submitted`, `approved`, `denied`, `checked_in`, `checked_out` and `archived`; show unknown values neutrally.

## 7. Rollout (design Migration Plan)

- [ ] 7.1 DEV:
  - deploy the API;
  - run the tenant upgrade;
  - restart the workers;
  - deploy the web;
  - run `scripts/qa_regression/run.py` and the e2e smoke against DEV.
- [ ] 7.2 STAGE: the same steps, then the app's test build against STAGE (sections 4 and 5).
- [ ] 7.3 PROD: only after the app developer has confirmed every item in section 4. Deploy the API in the migration window, then run the tenant upgrade, restart the workers and deploy the web. Watch for 429s on `/files` and `/form-builder/effective` for the first hour.
- [ ] 7.4 Strict mode: once the app release with section 5 is live for users, enable `PUBLIC_ENDPOINT_HARDENING` in STAGE and then PROD, and confirm no `Deprecation: true` traffic remains first.
