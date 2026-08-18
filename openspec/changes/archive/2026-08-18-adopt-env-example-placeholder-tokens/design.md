## Context

See `proposal.md` - Why for motivation. Current `.env.example` (21 settings)
mixes three kinds of value:
- **True secrets**: `JWT_SECRET_KEY` (already has a generation comment).
- **DDEV-fixed infra values**: `DATABASE_URL`, `REDIS_URL`,
  `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` — correct as shipped for
  anyone using this project's DDEV setup unmodified.
- **Product/business defaults**: `ACCESS_TOKEN_EXPIRE_MINUTES`,
  `INVITATION_TOKEN_TTL_HOURS`, etc. — same for every environment unless a
  deployment deliberately overrides them.

`README.md:22` currently reflects that mix: `cp .env.example .env # then set
a real JWT_SECRET_KEY` — implying everything else is already right. The
user's explicit choice (per the propose-phase clarification) is to flatten
this distinction: every value becomes a `__VARNAME__` placeholder, uniformly,
regardless of which of the three kinds it is.

## Goals / Non-Goals

**Goals:**
- Every setting in `.env.example` reads as `KEY=__KEY__`, **except** the 5
  fields carved out below (Decision 4) — those stay genuinely blank by
  design, not an oversight.
- No setting loses its explanatory comment in the process; any setting
  without one gets a short comment stating what real value belongs there,
  since the placeholder itself carries no information about the expected
  format/value anymore.
- `README.md`'s quick-start step reflects the new reality (fill in every
  placeholder, not just the JWT secret).

**Non-Goals:**
- Not building a secrets-generation script (explicitly declined during
  propose-phase clarification) — filling in real values stays a manual,
  per-developer step.
- Not changing `core/config.py`, the local `.env`, or any runtime behavior —
  `.env.example` is inert from the application's point of view.
- Not adopting the Symfony recipe's `###> package/name ###` /
  `###< package/name ###` block-marker convention — the user's example
  showed it, but the propose-phase clarification scoped this change to the
  placeholder *value* style only. `.env.example`'s existing section grouping
  (blank lines + prose comments) already serves the same purpose and stays
  as-is. Flagged here as a explicit exclusion, not an oversight.

## Decisions

**1. Placeholder token format matches the variable's own name, exactly as in
the user's example.**
`DATABASE_URL=__DATABASE_URL__`, `SMTP_PASSWORD=__SMTP_PASSWORD__`, etc. —
no abbreviation, no alternate casing. Trivial but worth stating so
implementation doesn't improvise a different token shape per variable.

**2. Every placeholder keeps (or gains) a comment stating the real value's
expected shape or a copy-pasteable default.**
For the 4 DDEV-fixed infra values and the product-default values that don't
yet have a comment (`APP_NAME`, `ENVIRONMENT`, `DEBUG`, `JWT_ALGORITHM`,
`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_MINUTES`,
`CORS_ALLOWED_ORIGINS`, `DEFAULT_TENANT_SLUG`, `SMTP_FROM_ADDRESS`,
`INVITATION_TOKEN_TTL_HOURS`, `INVITATION_MAX_UPLOAD_SIZE_BYTES`,
`INVITATION_MAX_GROUP_VISITORS`), add a one-line comment giving the value a
DDEV-default setup should actually use (e.g. `# db/db/db on host "db" —
DDEV's Postgres service` above `DATABASE_URL=__DATABASE_URL__`). Alternative
considered: leave these bare, since the proposal's own trade-off already
accepts that onboarding gets slower — rejected, because a bare placeholder
with zero hint (for a value that has one single correct answer for anyone
using this repo's DDEV config) would make the file actively unhelpful rather
than just less turnkey; the goal is "deliberate, not undiscoverable."

**4. Five fields are carved out of the "every value becomes a placeholder"
rule: `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMS_GATEWAY_BASE_URL`,
`SMS_GATEWAY_API_KEY`, `SMS_FROM_NUMBER` stay genuinely blank.**
Discovered during implementation, not anticipated at propose-time: these 5
fields are `str | None` settings where "unset" (`None`) and "empty string"
are functionally different to `pydantic-settings` — an env var *present*
with any non-empty value, including an un-filled-in placeholder token like
`__SMTP_USERNAME__`, is read as a real value, not as "absent." The
`pre-commit-quality-audit` change already hit this exact bug: a present-but-
empty `SMTP_USERNAME`/`SMTP_PASSWORD` made `aiosmtplib` attempt an AUTH login
with blank credentials, which mailpit rejects outright — a placeholder token
would trigger the identical failure (arguably worse, since it's an obviously-
wrong literal string rather than an empty one) for any developer who forgets
to blank these back out. Applying Goal 1 uniformly here would silently
reintroduce a bug this project already paid to fix once. These 5 lines stay
`KEY=` (blank) with a comment explaining why no placeholder belongs there,
cross-referencing the prior audit's fix — everything else follows Goal 1
without exception.

**3. `README.md`'s quick-start step is rewritten, not just re-worded.**
Current: `cp .env.example .env    # then set a real JWT_SECRET_KEY (see
comment in the file)`. New wording states every placeholder needs a value,
and points at the per-line comments (Decision 2) as the source for what to
put in the DDEV-fixed ones — so a new developer isn't left re-deriving
`postgresql+asyncpg://db:db@db:5432/db` from scratch.

## Risks / Trade-offs

- [Risk] A developer copies `.env.example` to `.env` without replacing every
  placeholder and the app fails to start (or fails a type-validation check
  in `pydantic-settings` for an int/bool field like `SMTP_PORT`/`DEBUG`) →
  Mitigation: this is the intended fail-fast behavior the user's requested
  convention is choosing over the current silent-defaults behavior; Decision
  2's per-line hints minimize how often this happens for values that have
  one obviously-correct answer.
- [Risk] Existing local `.env` files developers already have (untouched by
  this change) become inconsistent with the new `.env.example` shape over
  time (e.g. a new setting added later won't show its old-style default) →
  Mitigation: none needed now — `.env.example` additions going forward
  should follow this same placeholder convention, so drift is bounded
  to "old .env values are real, template values are placeholders," which is
  the expected steady state, not a bug.

## Migration Plan

1. Rewrite `.env.example` value-by-value (Decisions 1-2).
2. Update `README.md`'s quick-start step (Decision 3).
3. Confirm nothing in the app or test suite reads `.env.example` directly
   (expected: nothing does — `core/config.py`'s `env_file=".env"` is the only
   file `pydantic-settings` loads) so the full `pytest` suite is unaffected;
   run it once as confirmation.

**Rollback**: single-file textual revert (`git checkout .env.example
README.md` pre-commit, or a follow-up commit post-commit) — no code,
schema, or dependency changes involved.

## Open Questions

None — the propose-phase clarification already resolved both open questions
(placeholder scope: all values; mechanism: template-only, no generator
script).
