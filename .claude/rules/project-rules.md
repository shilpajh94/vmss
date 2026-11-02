---
trigger: always_on
---

# VMSS_API Project Rules

Adapted from a teammate's rules on another project (kept as reference at the repo
root: `database-architecture.md`, `fastapi-architecture.md`, `project-rules.md`,
`security-architecture.md`). Where this file deviates from that reference, the
reason is stated inline — don't silently revert to the old pattern.

## Project Overview

- **Product**: Visitor Management SaaS (VMSS) — backend API only. Web portal is
  React, mobile is Flutter; both are separate repos and consume this API over HTTP.
- **Tech Stack** (pinned to latest stable as of this writing — bump deliberately,
  not accidentally):

  | Component | Choice | Version |
  |---|---|---|
  | Language | Python | 3.13 (managed by `uv`, not the OS/container Python) |
  | Web framework | FastAPI | 0.141.x |
  | ASGI server | Uvicorn | 0.52.x |
  | ORM | SQLAlchemy (async) | 2.0.52 |
  | DB driver | asyncpg | 0.31.x |
  | Migrations | Alembic | 1.19.x |
  | Validation | Pydantic | 2.13.x |
  | Settings | pydantic-settings | 2.15.x |
  | Database | PostgreSQL | 17 |
  | Cache / broker | Redis | 8.x (via `ddev-redis` add-on) |
  | Background jobs | Celery | 5.6.x |
  | Auth tokens | PyJWT | 2.13.x |
  | Password hashing | argon2-cffi | 25.x |
  | Rate limiting | slowapi | 0.1.x |
  | Dependency manager | uv | 0.12.x |

- **Multi-tenancy**: schema-per-tenant from day one — a global Postgres schema
  for cross-tenant registry tables, plus one dedicated schema per tenant for
  its own domain tables. See `database-architecture.md` §2. Only one tenant
  exists today (`tenants` table); do not add code that assumes there's only
  ever one.

## Coding Standards

- **PEP 8, no exceptions, no camelCase in Python.** The reference project's rule
  ("camelCase for variables/functions in the API layer to match frontend
  expectations") is intentionally **not** carried over here — mixing naming
  conventions inside Python code is a PEP 8 violation and a lint-suppression
  headache. Instead: Python stays snake_case everywhere, and the JSON boundary is
  camelCase via Pydantic's `alias_generator` on a shared `CamelModel` base (see
  `fastapi-architecture.md` §3). React/Flutter get the camelCase they expect;
  the codebase stays idiomatic Python.
- **Type hints are mandatory** on every function signature (params + return type).
- **Docstrings**: only when the *why* isn't obvious from the name/types — same bar
  as inline comments. Don't restate what the code already says.
- **Formatting/linting**: `ruff` (lint + import sort) and `ruff format` (formatter).
  Do not add `black`/`isort` on top — `ruff` replaces both and is faster; running
  both is redundant and they can disagree.
- **Static typing**: `mypy` in CI, strict mode on `src/vmss_api/core` and any new
  module touching money/PII/auth; other modules may relax incrementally.

## Directory Structure

```
VMSS_API/
├── src/vmss_api/
│   ├── core/            # config, db session, tenancy, security, deps, responses, middleware
│   ├── auth/             # users, roles, permissions (tenant-scoped except the catalog), login
│   ├── tenant/            # the tenant registry itself (global schema) + its own profile endpoints
│   ├── platform/           # superadmin auth + tenant provisioning (global schema)
│   ├── org_structure/       # branch, building, floor, department, gate, desk (tenant-scoped, not yet built)
│   ├── visitors/              # visitor master data, visitor types, blacklist, watchlist
│   ├── invitations/          # pre-registration, QR, recurring invites
│   ├── approvals/             # configurable approval workflow engine
│   ├── checkin/                 # check-in/out, badges, overstay detection
│   ├── notifications/           # templates + multi-channel dispatch
│   ├── access_control/           # zones, gate/RFID/biometric integration hooks
│   ├── emergency/                  # "who's inside" real-time report
│   ├── reports/                     # analytics/read endpoints
│   ├── admin/                        # dynamic forms, holiday calendar, working hours config
│   ├── backend_pre_start.py            # waits for Postgres before prestart runs migrations
│   ├── api.py                           # aggregates every feature's router into api_router
│   └── main.py                           # FastAPI() instance, startup/shutdown, mounts api_router
├── alembic/                                # global-schema migrations
├── alembic_tenant/                          # tenant-schema migrations (run once per tenant)
├── scripts/                                  # lint.sh, format.sh, test.sh, prestart.sh, provision_tenant.py, seed_dev_data.py
├── tests/                                      # cross-feature/integration tests + conftest fixtures
├── .ddev/
├── pyproject.toml
├── .aiignore
└── .env.example
```

Note the distinction: `tenant/` answers "which tenant is this" (the SaaS
account/schema boundary — global schema). `org_structure/` (not yet built)
answers "what does this tenant's own org chart look like" (branch, building,
floor, department, gate, desk — tenant-scoped tables, living in each
tenant's own schema like `visitors`/`invitations` will). Don't fold the
latter into `tenant/` when it gets built — they're different concepts that
happened to share a name (`organizations/`) before this rename.

Everything nests under the single top-level package `vmss_api` (not multiple
top-level packages like the reference project's `src/app` + `src/<feature>`
siblings). One package means one clean import path everywhere — no
`try: from app.x import y / except ModuleNotFoundError: from src.app.x import y`
fallback hack. See `fastapi-architecture.md` §1.

## Dependency Management

- **`uv`**, not `pip freeze > requirements.txt`. `pyproject.toml` declares
  dependencies; `uv.lock` pins the exact resolved graph (commit both). `uv` also
  pins and installs the Python interpreter itself (3.13), so we're not at the mercy
  of whatever Python ships in the base container image.
- Add a dependency: `uv add <package>`. Add a dev-only dependency: `uv add --dev <package>`.
- Never hand-edit `uv.lock`.

## Local Development

- **DDEV**, not a manually-activated venv. Every command runs through
  `ddev exec uv run <command>` (or a `ddev` custom command shortcut — see
  `VMSS_API/.ddev/commands/`). This replaces the reference project's
  "activate venv before every command" rule — DDEV's container *is* the
  consistent environment, so there's nothing to remember to activate.
- `ddev start` brings up the API container, PostgreSQL 17, and Redis together.

## Testing

- `pytest` + `pytest-asyncio` + `httpx.AsyncClient` against the FastAPI app.
- Tests run against a real PostgreSQL database (a dedicated `vmss_test` DB on the
  same DDEV Postgres instance), not mocks or SQLite — SQLAlchemy dialect quirks
  (JSONB, array columns, `ON CONFLICT`) don't show up under SQLite and would give a
  false sense of safety.
- Run: `ddev exec uv run pytest`. While implementing a change request or
  suggestion, run only the changed feature's tests plus those of any area that
  depends on the changed code — not the full suite (`testing-standards.md` §5).
  The full suite is the CI gate's job (`git-workflow.md` §4), or run it when
  explicitly asked.

## New Features

- **Location**: `src/vmss_api/<feature>/` — new top-level feature package.
- **Required files**: `__init__.py`, `router.py`, `service.py`, `schemas.py`,
  `models.py` (if it owns tables), `repository.py` (if it owns tables), `tests.py`
  or a `tests/` subpackage.
- **Integration**: register the router in `src/vmss_api/api.py` via
  `api_router.include_router(<feature>.router.router)`.
- **Consistency**: use `success_response`/`error_response` from
  `vmss_api.core.responses` for every JSON endpoint (see
  `fastapi-architecture.md` §3).
- **Documentation**: add a short markdown file under `docs/features/` describing
  purpose, endpoints, and any config knobs — same expectation as the reference
  project.

## Secret Management

- All credentials/keys live in `.env`, loaded via `pydantic-settings` into the
  `settings` object in `src/vmss_api/core/config.py`. `.env` is gitignored;
  `.env.example` is committed and kept in sync with every new setting.
- Details: `security-architecture.md`.

## Deployment

- **Target**: not yet decided (client/infra decision pending — flag this as open
  rather than guessing). Whatever it is, the container must run `uv sync --frozen`
  then `uv run alembic upgrade head` before starting `uvicorn`.
- No automatic deploy is configured yet — don't assume merge-to-main deploys until
  a pipeline is actually wired up.
