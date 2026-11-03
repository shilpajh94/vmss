## Context

Findings from the codebase that shape the design:

- A "visit" is an `Invitation` row; there is no visits table. `{invitation_id}` is the visit id.
- There is no visitors master table. The visitor-level record is `invitation_visitors` (co-visitors of `group` invitations only). An `individual` invitation's primary contact is columns on `invitations` and has no visitor id.
- Visit milestones are already recorded in `audit_logs` (`entity_type`, `entity_id`, `action`, `actor_user_id`, `diff`, `created_at`), with index `(entity_type, entity_id, created_at)`. Actions seen: `invitation_created`, `walk_in_registration_created`, `invitation_approved`, `invitation_denied`, `invitation_approval_reverted`, `visit_id_verified`, `visit_photo_captured`, `invitation_checked_in`, `invitation_qr_checked_in`, `invitation_code_checked_in`, `invitation_checked_in_public`, `invitation_checked_out`, `invitation_qr_checked_out`, `invitation_code_checked_out`, `invitation_auto_checked_out`, `badge_printed`, `badge_reprinted`, `badge_*` scan actions, and others.
- `entity_type` is **inconsistent**: `"Invitation"` is written ~24 times, `"invitation"` ~3 times. A filter on one spelling silently drops events.
- `badge_prints` (append-only: `visit_id`, `printed_by_user_id`, `printed_at`, `jti`, `active`, `reprint_reason`) is the authoritative record of prints and reprints.
- `notifications` is one row per recipient with `invitation_id` (indexed, FK cascade), `dispatch_id`, `title`, `body`, `created_at`. One dispatch fans out to many rows.
- Task 2.3 names `visit_info` as a source. That package holds visit purposes and durations only; it has no events.
- Pagination uses `core/deps.py::get_pagination`, responses use `paginated_response` / `PaginatedEnvelope`, sorting uses `order_clause` and a whitelisted enum, as in `audit_trail/`.
- No feature flag (decision with the user); the endpoints are permission-gated only. Subtask 2.1's flag is dropped and its scaffold is part of this change.

## Goals / Non-Goals

**Goals:**
- One ordered, paginated, read-only history per visit, built with a constant number of queries.
- No new tables, no new audit writes, no change to existing endpoints.
- PII-safe by construction: the response schema cannot carry raw diffs or tokens.

**Non-Goals:**
- Zone entry/exit and overstay events (no data source; omitted by decision).
- Backfilling or rewriting history; legacy visits show only what was recorded.
- Streaming/real-time updates.
- Per-visitor event attribution inside a group visit (see Decision 6).

## Decisions

**1. Events come from three tables, mapped in one place.** A module-level mapping `AUDIT_ACTION_TO_EVENT: dict[str, TimelineEventType]` is the only place audit actions are interpreted. Check-in and check-out variants all map to `checked_in` / `checked_out`. Unmapped actions are excluded by a `WHERE action IN (...)` on the mapped keys, so the database never returns rows the timeline would discard. Adding a future event type is one enum member plus one mapping entry. Alternative of exposing raw `action` strings rejected: it leaks internal naming into a client contract.

**2. Badge events from `badge_prints` only.** `badge_printed` / `badge_reprinted` also exist as audit actions. Reading both would show every print twice. `badge_prints` wins because it is the system of record and carries `reprint_reason`. The first row for a visit is `badge_printed`; rows with `reprint_reason IS NOT NULL` are `badge_reprinted`. Badge audit actions are excluded from the audit branch of the query. Badge-scan check-out/re-entry audit rows are mapped (`checked_out`; re-entry mapped to `checked_in`) because they have no `badge_prints` counterpart.

**3. Notifications deduplicated by dispatch.** `SELECT DISTINCT ON (dispatch_id)` (earliest row) so a three-recipient dispatch is one event. Only the notification's `title` is used for the summary, passed through masking; `body` is never returned because bodies can embed visitor names and contact details.

**4. One merged query, sorted and paginated in SQL.** A `UNION ALL` of three selects projecting the same columns (`occurred_at`, `event_type`, `source`, `source_id`, `actor_user_id`, `summary`, `detail`) is wrapped as a subquery; the outer query applies the date filter, `ORDER BY`, `LIMIT/OFFSET`, and a separate `count(*)` over the same filtered subquery. Sorting in Python after fetching everything was rejected: it breaks `total` and pagination at scale. Tie-break is `(occurred_at, source, source_id)` so pages are stable. Each branch is constrained to the one visit, so all three use existing indexes: audit `(entity_type, entity_id, created_at)`, `badge_prints.visit_id`, `notifications.invitation_id`. No new index.

**5. Audit `entity_type` matched as `IN ('Invitation', 'invitation')`.** Not `lower(entity_type) = 'invitation'`, which cannot use the composite index. Normalizing the 3 odd write sites is a separate cleanup and out of scope; the timeline tolerates both until then. Noted as a risk.

**6. Visitor endpoint resolves to the invitation.** `GET /visitors/{visitor_id}/timeline` looks up `invitation_visitors.id`, gets its `invitation_id`, and returns that invitation's timeline through the same service function. Audit rows are invitation-level, so the events are the visit's, not filtered per co-visitor. The visitor lookup is one query; a missing id is `404`. Primary contacts of `individual` invitations have no visitor id and use the invitation endpoint (open item in proposal).

**7. Actors in one batched lookup.** After the page is fetched, collect distinct `actor_user_id`s and run one `SELECT id, full_name FROM users WHERE id IN (...)`. Only the display name is exposed. A deleted or unknown actor yields `null`. This is a single repository method, not a per-row `get`.

**8. Safe response schema, not a scrub step.** `TimelineEventOut(CamelModel)` has exactly: `event_type`, `occurred_at`, `summary`, `actor_name`. There is no `diff`, `detail`, token or storage-key field to leak. Summaries are built from fixed templates (for example "Badge reprinted: <reason>"); the only free text is the reprint reason (length-capped at write time already) and the notification title, both passed through `core/masking.py` helpers for email/phone patterns. Alternative of returning `diff` for admins rejected: nothing here needs it and `diff` can hold field values.

**9. Permission `timeline:view`.** Added to `auth/rbac_catalog.py`, granted to Admin, Reception, Security, with a tenant migration for existing roles (follow earlier `grant_*` migrations). Enforced with `Depends(require_permission("timeline:view"))` on both routes. Chosen over reusing `invitations:view` because a timeline exposes actor names and notification activity, which warrants its own grant. Open item: confirm the role list.

**10. No flag.** The feature ships enabled; the permission is the only gate. Rollback is revoking `timeline:view` or reverting the deploy.

**11. Layering and docs.** Router calls service, service calls repository, repository is the only `AsyncSession` user (`fastapi-architecture.md` §2). Routes declare `response_model=PaginatedEnvelope[TimelineEventOut]` and `-> JSONResponse`. A new feature package `timeline/` (router without prefix, full paths `/invitations/{id}/timeline` and `/visitors/{id}/timeline`) is registered in `api.py` with a `timeline` entry in `_TAGS_METADATA`. `tests/test_api_documentation.py` must still pass.

## Risks / Trade-offs

- **Inconsistent `entity_type` casing** → handled by matching both spellings; a future third spelling would be missed. Mitigation: the matched spellings live in one constant (`timeline/mapping.py::INVITATION_ENTITY_TYPES`).
- **Audit coverage gaps** → events not audited today (for example any path that updates `checked_in_at` without an audit row) will not appear. The timeline is only as complete as the audit trail; documented in `docs/features/timeline.md`. Not backfilled.
- **Photo-captured has no timestamp column** → the timeline depends on the `visit_photo_captured` audit row; legacy photos without it show no event.
- **OFFSET pagination on a union** → fine at per-visit volumes (tens to low hundreds of events); no cursor needed (`api-conventions.md` §1).
- **Notification summaries may still contain PII beyond email/phone patterns** (a name in a title) → titles are templates in current code; the test suite pins that. Revisit if free-text titles are introduced.
- **Group-visit attribution** → per-co-visitor filtering is not possible from invitation-level audit rows; the visitor endpoint intentionally returns the visit's timeline.

## Migration Plan

1. Tenant migration granting `timeline:view` to existing Admin/Reception/Security roles; downgrade removes the grants.
2. Deploy. Rollback is reverting the deploy or revoking the permission; nothing else changed.

## Open Questions

- Confirm `timeline:view` role grants (Admin, Reception, Security).
- Confirm primary contacts of individual invitations are served only by the invitation endpoint.
- Confirm reading milestones from `audit_logs` rather than `visit_info`.
