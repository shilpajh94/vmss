## 1. Domain and adapter

- [x] 1.1 In `src/domain/entities/staff-user-schema.ts`, replace `role: z.string().min(1)` with `roles: z.array(z.string().min(1))`
- [x] 1.2 In `src/infrastructure/staff-auth-repository.ts` `getCurrentUser`, set `roles` to the distinct `roleName`s from `branchRoles` in order, falling back to `['Staff']` when empty

## 2. Top bar

- [x] 2.1 In `src/presentation/components/AppTopBar.tsx`, render `currentUser.roles.join(', ')` in the role line with `truncate`, a max width, and a matching `title`

## 3. Verification

- [x] 3.1 Run `npx tsc -b` and fix any other `StaffUser` consumers or fixtures
- [x] 3.2 Run `npm run lint` and `npm run build`
- [ ] 3.3 Manually check with a multi-role user (e.g. reception + another role), a single-role user, and a narrow desktop width
