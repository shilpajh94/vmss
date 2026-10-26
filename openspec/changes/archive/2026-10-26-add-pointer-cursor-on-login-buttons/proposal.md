## Why

On the admin (`/admin/login`) and staff (`/staff/login`) sign-in screens, the mouse pointer stays an arrow when it is over the sign-in buttons. The links on those screens already show the hand pointer, so the buttons look like they cannot be clicked. The cause is that Tailwind v4's base styles no longer give `<button>` elements `cursor: pointer`, and these buttons never add it back.

## What Changes

- On `/admin/login`, the **Sign In** and **Sign in with SSO** buttons show the hand (pointer) cursor on hover.
- On `/staff/login`, the **Sign in with SSO** button shows the hand cursor on hover.
- While a button is disabled (a sign-in or SSO redirect is in progress), it shows the not-allowed cursor instead of the hand, so the cursor never suggests a click that will do nothing.
- Links that already show the hand cursor ("Contact System Administrator", footer links) stay as they are.
- No other screens change. Buttons elsewhere in the app keep their current per-component cursor styling.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `staff-login`: adds a requirement that the `/admin/login` sign-in actions show the pointer cursor (not-allowed while disabled).
- `staff-sso-login`: adds a requirement that the `/staff/login` SSO action shows the pointer cursor (not-allowed while disabled).

## Impact

- Code: `src/presentation/pages/staff-login/Components/LoginFormCard.tsx` and `src/presentation/pages/staff-sso-login/Components/SsoSignInCard.tsx` (className additions only).
- Tests: one e2e check in `e2e/test_auth_and_dashboards.py` that reads the buttons' computed cursor.
- The fix is applied per button, following the ~20 components that already add `cursor-pointer` themselves. It is not a global CSS rule for all buttons, so the change stays limited to the login screens (see the Approach note in tasks.md).
- No API, dependency, or routing changes.
