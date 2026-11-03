# Visit Timeline

Read-only, chronological history of one visit. Merges existing records; it
writes nothing and adds no tables. Gated by permission only (`timeline:view`,
granted to Admin, Reception and Security) — there is no feature flag.

## Endpoints

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/invitations/{invitationId}/timeline` | `timeline:view` | Events for one visit (an invitation). |
| GET | `/api/v1/visitors/{visitorId}/timeline` | `timeline:view` | `visitorId` is an `invitation_visitors.id` (a co-visitor of a group invitation); returns the timeline of the invitation that visitor belongs to. |

An unknown id, or one belonging to another tenant, returns `404`. A primary
contact of an `individual` invitation has no visitor id; use the invitation
endpoint.

### Query parameters

| Param | Default | Notes |
|---|---|---|
| `page`, `pageSize` | `1`, `20` | `pageSize` max 100. |
| `occurredAfter`, `occurredBefore` | none | Inclusive datetimes. |
| `sortBy` | `occurred_at` | `occurred_at` or `event_type`; anything else is `422`. |
| `sortOrder` | `desc` | `asc` or `desc`. |

Response: `PaginatedEnvelope` of `{eventType, occurredAt, summary, actorName}`.
Ties are ordered by a stable secondary key, so paging never repeats or skips.

## Event types and sources

| Event | Source |
|---|---|
| `invited` | audit: `invitation_created`, `walk_in_registration_created` |
| `approved` / `denied` / `approval_reverted` | audit: `invitation_approved` / `invitation_denied` / `invitation_approval_reverted` |
| `id_verified` | audit: `visit_id_verified` |
| `photo_captured` | audit: `visit_photo_captured` |
| `checked_in` | audit: `invitation_checked_in`, `_qr_`, `_code_`, `_public`, `badge_checked_in`, `badge_re_entered` |
| `checked_out` | audit: `invitation_checked_out`, `_qr_`, `_code_`, `_auto_`, `badge_checked_out` |
| `badge_printed` / `badge_reprinted` | `badge_prints` (reprint = row with a reason); legacy PNG badge audit rows `invitation_badge_issued` / `invitation_badge_reprinted` |
| `notification_sent` | `notifications`, one event per dispatch (not per recipient) |

The new badge flow's own `badge_printed`/`badge_reprinted` audit rows are
ignored, because `badge_prints` already records them. Audit rows are matched
on `entity_type` of `Invitation` or `invitation` (both spellings exist).
Zone entry/exit and overstay are not event types yet — no data source exists.

## Privacy

The response has no raw audit `diff`, ID numbers, tokens or storage keys.
Emails and phone numbers inside a notification title or reprint reason are
masked, and notification bodies are never returned. The only identity exposed
is the acting user's display name.

## Limitations

The timeline is only as complete as what was recorded: an action that was
never audited does not appear, and nothing is backfilled. Photo-captured has
no timestamp column of its own and relies on its audit row.
