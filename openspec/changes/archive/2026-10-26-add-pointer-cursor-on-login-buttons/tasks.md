> Approach: add `cursor-pointer disabled:cursor-not-allowed` to each button's own className. This follows the existing per-component convention and keeps the change limited to the two login screens. design.md was skipped because the change is two className edits.

## 1. Admin login (`/admin/login`)

- [x] 1.1 In `src/presentation/pages/staff-login/Components/LoginFormCard.tsx`, add `cursor-pointer disabled:cursor-not-allowed` to the "Sign In" `PendingButton` className
- [x] 1.2 In the same file, add `cursor-pointer disabled:cursor-not-allowed` to the "Sign in with SSO" `<button>` className

## 2. Staff login (`/staff/login`)

- [x] 2.1 In `src/presentation/pages/staff-sso-login/Components/SsoSignInCard.tsx`, add `cursor-pointer disabled:cursor-not-allowed` to the "Sign in with SSO" `PendingButton` className

## 3. Verification

- [x] 3.1 In `e2e/test_auth_and_dashboards.py`, add a test that opens `/admin/login` and `/staff/login` and checks that each sign-in button's computed `cursor` is `pointer` (no login attempt, so the API login rate limit is not used)
- [x] 3.2 Run only that e2e test module and `npm run lint` / type check; don't run the full suite
- [ ] 3.3 Manually hover each button in the browser in light and dark mode and confirm the hand cursor appears
