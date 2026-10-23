## 1. Revert the uncommitted "Clear all" code

- [x] 1.1 Confirm with `git diff` that every change in the eight files below is clear-all code (nothing else was edited in them since `HEAD`)
- [x] 1.2 `git restore` those eight files: `e2e/test_notification_bell.py`, `src/composition-root.ts`, `src/data/api/api-endpoints.ts`, `src/data/repositories/notification-repository.ts`, `src/domain/entities/notification-feed-schema.ts`, `src/infrastructure/notification-repository.ts`, `src/presentation/components/notification-bell/NotificationBell.tsx`, `src/presentation/context/notification-center-context.tsx`. Leave `.env` alone
- [x] 1.3 Delete the untracked `src/data/use-cases/clear-all-notifications.ts`; `grep -rni "clearAll\|clear all\|CLEAR_NOTIFICATIONS" src e2e` must come back empty

## 2. Verify

- [x] 2.1 `git status --short` shows only `.env` and this change folder
- [x] 2.2 `npx tsc -b` and `npm run lint` pass (no prettier); the full unit/e2e suites aren't needed for a revert to `HEAD`
- [x] 2.3 `openspec validate prune-orphaned-notifications --strict`
