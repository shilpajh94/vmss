---
trigger: model_decision
description: Apply when adding or modifying logging statements, request-handling middleware, or code that dispatches a Celery task — anything that needs to be traceable across a request or worker boundary.
---

# Logging & Observability Conventions — VMSS_API

`security-architecture.md` §5 covers *what* gets audited (mutations, security
events). This covers *how* logs stay traceable across layers and into background
workers, and what fields every log line carries.

## 1. Request/Correlation ID

- `core/middleware.py` extracts `X-Request-ID` from the inbound request if present,
  otherwise generates one, and binds it into `structlog`'s contextvars at the start
  of the request. Every log line emitted for that request — router, service,
  repository — inherits it automatically; no need to pass it as an explicit
  parameter through every function signature.
- The response echoes the same value back in an `X-Request-ID` header, so a client
  bug report ("check-in failed at 10:42") can be traced to exact server-side logs.
- When a request enqueues a Celery task (notification dispatch, report generation),
  pass the request id as a task argument and re-bind it into `structlog`'s context
  at the top of the task body. Without this, a failed notification send is
  untraceable back to the check-in event that triggered it.

## 2. Standard Log Fields

Every log line carries, where applicable: `request_id`, `tenant_id`,
`user_id` (if authenticated), `branch_id` (if the request resolved a branch
context via `X-Branch-ID` — see `org_structure/deps.py::get_branch_context`,
bound the same way `get_current_user` binds `tenant_id`/`user_id`). Never
include: identity document numbers,
raw OTP codes, JWT/refresh token values, or full request bodies containing PII —
consistent with `security-architecture.md` §2's "never log OTP in plaintext, not
even at DEBUG."

## 3. Log Level Policy

| Level | Use for |
| :--- | :--- |
| `DEBUG` | Dev-only diagnostic detail (query params, intermediate values). Never enabled in staging/prod by default. |
| `INFO` | Business events worth a normal operational trail (invitation sent, visitor checked in, report generated). |
| `WARNING` | Recoverable anomalies (rate-limit trip, failed login, permission denial, Celery task retry). |
| `ERROR` | Unhandled exceptions caught by the global handler, Celery task exhausting retries — anything that needs a human to look. |

All of the above goes through the centralized `structlog` logger from `core/`.
Never `print()`, never a bare `logging.getLogger(__name__)` configured ad hoc in a
feature module — that bypasses the request-id binding in §1.
