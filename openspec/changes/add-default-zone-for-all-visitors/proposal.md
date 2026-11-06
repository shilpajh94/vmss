## Why

Zone access is **default deny**: a visit with no per-invitation zones and no visitor-category defaults is refused every zone (`add-zone-access-control`, Decision 3). When reception forgets to assign zones, a legitimate, approved visitor is turned away at every door, including common areas everyone should reach (lobby, cafeteria). Sites want one **default zone** that every visitor of the branch can always enter, so a forgotten assignment is no longer a lockout.

## What Changes

- Add `zones.is_default` (boolean, default false). At most one live default zone per branch, enforced by a partial unique index.
- Effective allowed zones become: (the invitation's own zones, else the visitor category's defaults) **plus** the visit's branch default zone, if one exists and is live and active. The default zone is a union member, not just a fallback.
- Zone create/update accept `isDefault`; setting it on a zone clears it on the branch's previous default in the same transaction. `ZoneOut` returns `isDefault`; zone list gains an `isDefault` filter.
- A default zone cannot be deleted or deactivated until another default is chosen or the flag is cleared (409).
- Both entry paths pick this up through the one shared resolver: the gate scan (`POST /api/v1/access/scan`) and the front-desk check-in zone enforcement.
- Tests, `docs/features/access_control.md` update, and a tenant migration.

Additive. No default zone configured means behavior is identical to today. Toggle off means nothing changes.

## Capabilities

### Modified Capabilities
- `zone-access-control`: new default-zone requirement, and the effective-allowed-zones rule now includes it.

## Impact

- Code: `access_control/` (`models.py`, `schemas.py`, `repository.py`, `service.py`, `checkin_gate.py`), `docs/features/access_control.md`.
- Database: tenant migration adds `zones.is_default` and the partial unique index `(branch_id) WHERE is_default AND deleted_at IS NULL`. No data backfill; no zone is default until an admin sets one.
- API: additive field `isDefault` on zone request/response and a list filter. No breaking change, so stays in `/api/v1`.
- Frontend (separate repos): "Make default zone" toggle in zone admin; optional hint on the invitation zone picker.

## Out of scope

- Visitor-category-specific or per-visitor-type default zones (categories already have their own defaults).
- Bypassing any other `can_enter` rule. The default zone only widens the *allowed set*: gate link, check-in, approval, blacklist and time-window checks all still apply.
- Auto-creating a default zone for existing branches.

## Assumptions (change if wrong)

- The request was garbled. Read as: *one default zone, available to every visitor automatically, even when reception assigns no zones.*
- **Always included, not fallback-only.** Reception's explicit list still narrows access to other zones, but never removes the default zone. If you want it to apply only when nothing is assigned, say so; it is a one-line change in the resolver.
- **Default is per branch**, since zones belong to a branch and `can_enter` rejects cross-branch zones.
- A default zone still needs a gate link (`zone_gates`) to be enterable at a door scan.
