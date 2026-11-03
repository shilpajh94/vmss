## 1. Event model and mapping (task 2.2)

- [x] 1.1 Add `TimelineEventType` enum (`invited`, `approved`, `denied`, `approval_reverted`, `id_verified`, `photo_captured`, `checked_in`, `checked_out`, `badge_printed`, `badge_reprinted`, `notification_sent`) in the timeline module's `schemas.py`; scaffold `src/vmss_api/timeline/` (`__init__`, `router`, `service`, `schemas`, `repository`) and register it in `api.py` and `_TAGS_METADATA`
- [x] 1.2 Add `AUDIT_ACTION_TO_EVENT` mapping (all check-in/out variants, approval, denial, revert, created/walk-in as `invited`, `visit_id_verified`, `visit_photo_captured`, badge-scan check-out/re-entry); exclude `badge_printed`/`badge_reprinted` audit actions
- [x] 1.3 Add `TimelineEventOut(CamelModel)` with only `event_type`, `occurred_at`, `summary`, `actor_name`; add the sort enum (`occurred_at`, `event_type`)
- [x] 1.4 Add summary builders from fixed templates; route reprint reason and notification title through `core/masking.py` email/phone masking

## 2. Merged query (task 2.3)

- [x] 2.1 Add `TimelineRepository` (only `AsyncSession` user): `UNION ALL` of audit, `badge_prints`, `notifications` branches projecting identical columns; audit branch filters `entity_type IN ('Invitation','invitation')` and mapped actions only
- [x] 2.2 Notifications branch uses `DISTINCT ON (dispatch_id)` so a fan-out dispatch is one event; select title only, never body
- [x] 2.3 Outer query: `occurredAfter`/`occurredBefore` filter, `order_clause` with tie-break `(occurred_at, source, source_id)`, `LIMIT/OFFSET`, and a matching `count(*)` over the same filtered subquery
- [x] 2.4 Add one batched actor lookup (`users WHERE id IN (...)`, display name only); no per-row `get`
- [x] 2.5 Add `service.get_timeline(...)` and a visitor-to-invitation resolver (`invitation_visitors.id -> invitation_id`, one query); both raise not-found for unknown ids

## 3. Endpoints and permission (task 2.4)

- [x] 3.1 Add `timeline:view` to `auth/rbac_catalog.py` (Admin, Reception, Security) and a tenant migration granting it to existing roles, with downgrade
- [x] 3.2 Add `GET /invitations/{invitation_id}/timeline` with `get_pagination`, date filters, `sortBy`/`sortOrder` enums, `require_permission("timeline:view")`, `response_model=PaginatedEnvelope[TimelineEventOut]`, `-> JSONResponse`, `paginated_response`
- [x] 3.3 Add `GET /visitors/{visitor_id}/timeline` with the same contract, resolving through the visitor lookup
- [x] 3.4 Confirm router registration, tags and `tests/test_api_documentation.py` pass; camelCase renders in `/docs`
- [x] 3.5 Log `timeline_viewed` at INFO via structlog with `tenant_id`, `user_id`, entity id and result count; no summaries or PII in the log

## 4. Tests and docs (task 2.5)

- [x] 4.1 Test ordering: default newest-first, `asc`, `sortBy=event_type`, stable paging across equal timestamps (every event exactly once)
- [x] 4.2 Test mapping and merge: check-in variants collapse, badge shown once (from `badge_prints`), reprint includes reason, fan-out notification collapsed, unmapped audit action excluded, both `entity_type` spellings included
- [x] 4.3 Test query count is constant for page sizes 5 and 50 (no N+1)
- [x] 4.4 Test date range filter and `total`; `sortBy` outside the whitelist returns `422`
- [x] 4.5 Test PII: no `diff`, phone/email masked in notification summary, no token/storage-key fields in the schema
- [x] 4.6 Test permission-denied (`403` without `timeline:view`) on both endpoints, plus the happy path for each
- [x] 4.7 Test tenant isolation using `make_tenant_schema`/`open_tenant_session`: tenant A cannot reach tenant B's invitation or visitor (`404`)
- [x] 4.9 Test unknown invitation id and unknown visitor id return `404`
- [x] 4.10 Write `docs/features/timeline.md`: event types and sources, endpoints, query params, permission, masking, and the audit-coverage limitation
- [x] 4.11 Run targeted tests only (timeline module, `auth` for the permission catalog, `tests/test_api_documentation.py`, tenant migration check) as one sequential `ddev exec uv run pytest <paths>`; report modules run and dependents included
