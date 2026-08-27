# Reports

Read-only cross-branch aggregation for admins. Doesn't own any table — it
queries across `org_structure`'s and `auth`'s tenant-scoped tables the same
way `auth/repository.py`'s `UserRepository.list_employees_page` already
joins into `org_structure` models directly (`fastapi-architecture.md`'s
layering still applies: `router.py` calls `service.py`, `service.py` calls
`repository.py`, only `repository.py` touches `AsyncSession`).

## Why a structural rollup, not a visit-activity rollup

"Cross-branch reporting rollup" could eventually mean visitor traffic,
check-in/out counts, or overstay rates per branch — but no `checkin`/
`invitations`/`approvals` feature exists yet (`project-rules.md`'s
directory-structure note), so there's no visit data to aggregate. This
report instead rolls up what already exists today: each branch's org-chart
footprint (buildings/floors/departments/reception desks/security gates) and
active employee headcount. Revisit once `checkin` lands — visit-activity
metrics belong here too, alongside the structural counts, not as a
replacement for them.

## Endpoint

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/reports/branches/rollup` | `reports:view` (company-wide) | Per-branch building/floor/department/desk/gate/active-employee counts, plus tenant-wide totals. |

Company-wide, not branch-scoped (`require_permission`, not
`require_branch_permission`) — the entire point is comparing across every
branch in one response, the same posture Branch CRUD itself takes
(`org_structure/router.py`).

## Query shape

`repository.py::BranchRollupRepository` issues one `GROUP BY branch_id`
aggregate query per entity type (buildings, floors via a join through
`Building`, departments/desks via a join through `Floor` → `Building`,
gates directly, active employees via a join through `Department` → `Floor`
→ `Building`) — never a per-branch loop, per `query-performance.md` §2.
`service.py::get_cross_branch_rollup` merges the six count dicts against
the branch list in Python and sums the tenant-wide totals.

## Scheduled snapshot (API-17)

In addition to the on-demand endpoint above, `tasks.py` runs the same
rollup automatically once a day and emails a summary to every Admin-role
user in each active tenant — see `docs/features/background-jobs.md` for
the job-runner mechanics (beat schedule, per-tenant fan-out, idempotency).
`repository.py::BranchRollupRepository.admin_users()` resolves the
recipient list — a role-membership query, not a permission check, since
the job runs unattended with no caller to authorize.
