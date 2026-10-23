## Why

The paired API change (`VMSS_API`, `prune-orphaned-notifications`) fixes
the inflated bell count at the source: it deletes notifications left
behind by deleted invitations and stops new ones from piling up. A first
pass of that work also added a "Clear all" button here, which permanently
deleted every notification. It was dropped before commit (API design.md
D5). Once the stale rows are gone, "Mark all read" already zeroes the
badge, and an irreversible delete one click from the bell isn't worth its
risk.

So this change has nothing to add to the portal. It only removes the
uncommitted "Clear all" edits, leaving the web app exactly as it is on
the branch today.

## What Changes

- Revert the uncommitted "Clear all" code: the endpoint entry, response
  schema, repository method, use case, composition-root wiring,
  notification-center `clearAll`, the bell button and confirm dialog, and
  the clear-all e2e test.
- No behaviour change versus the committed portal. "Mark all read" is
  untouched, and the badge shows the corrected count as soon as the API
  change is deployed.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

_None._ No spec-level behaviour changes (`skip_specs: true`).

## Impact

- **Code**: restores to `HEAD` `e2e/test_notification_bell.py`,
  `src/composition-root.ts`, `src/data/api/api-endpoints.ts`,
  `src/data/repositories/notification-repository.ts`,
  `src/domain/entities/notification-feed-schema.ts`,
  `src/infrastructure/notification-repository.ts`,
  `src/presentation/components/notification-bell/NotificationBell.tsx`,
  `src/presentation/context/notification-center-context.tsx`; deletes the
  untracked `src/data/use-cases/clear-all-notifications.ts`.
- **Not touched**: `.env` (a local modification that predates this work,
  never staged).
- **Release**: nothing to ship. After the revert this change can be
  deleted rather than archived.
