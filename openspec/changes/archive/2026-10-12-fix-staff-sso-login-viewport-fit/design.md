## Context

`StaffSsoLoginPage` (`src/presentation/pages/staff-sso-login/staff-sso-login.tsx`) has the same shell `/admin/login` had before `fix-admin-login-fit-viewport`. It is a `min-h-screen` flex column: header, then `main` (`flex-1`, `py-12 md:py-[120px]`, `justify-center`), then footer. `min-h-screen` only sets a floor, so the page grows to fit its content. The reporter's screenshots (1920×870 viewport) show:

| Part | Approx. height at ≥ md |
|---|---|
| `StaffPortalHeader` (`py-5` + logo) | ~90px |
| `main` vertical padding (`md:py-[120px]`) | 240px |
| `SsoSignInCard` (`md:p-12`, `md:gap-8`, badge, title, button, MFA note) | ~440px |
| `main` gap + "Need help?" line | ~52px |
| `StaffSsoLoginFooter` (`py-6`) | ~80px |
| **Total** | **~900px** vs ~870px visible |

The SSO card is shorter than the admin card because it has no email/password fields and no field-level validation errors. The 240px of fixed padding is still what causes the overflow.

`/admin/login` already contains the target pattern, and the `short` (`max-height: 900px`) / `xshort` (`max-height: 800px`) custom variants already exist in `src/styles/index.css`. See the archived `2026-10-12-fix-admin-login-fit-viewport/design.md` for the measured rationale behind those thresholds.

## Goals / Non-Goals

**Goals:**
- `/staff/login` behaves exactly like `/admin/login` with respect to viewport fit (see the spec scenarios).
- Reuse the existing variants and class patterns, so the two login pages stay visually and structurally consistent.

**Non-Goals:**
- Redesigning the card, changing copy, or touching SSO start/complete behaviour (`use-staff-sso-login-page.ts`).
- Extracting a shared gateway-shell component for both login pages. The admin change set this aside "until `/staff/login` gets the same fix". It is now possible, but it is not done here, to keep this change a minimal layout fix. Recorded as a follow-up below.
- Any VMSS_API change.

## Decisions

### 1. Copy the admin page's shell verbatim

- Root: `relative flex h-dvh w-full flex-col overflow-hidden` (replaces `min-h-screen`).
- `StaffPortalHeader` / `StaffSsoLoginFooter`: add `shrink-0`, so they keep their height when `main` has to give space up.
- `main`: `relative min-h-0 flex-1 overflow-y-auto`. Without `min-h-0`, the flex child keeps its content height and never scrolls.
- Inner wrapper `div`: `flex min-h-full flex-col items-center justify-center gap-4 md:gap-6 xshort:gap-3 md:xshort:gap-3 px-4 md:px-12 py-6 md:py-8 xshort:py-4 md:xshort:py-4`. Content is centered when it fits. When it overflows, the wrapper grows and `main` scrolls from the top. Putting `justify-center` directly on a scroller would push the top of the content out of reach.
- **Alternative considered:** only shrinking `md:py-[120px]`. That would fix 1920×870, but the footer would still scroll away on shorter screens, and the spec requires header and footer to stay in place. It would also leave the two login pages inconsistent.

### 2. Height-tier spacing on the card, header, and footer

Mirror the admin card's tiers on `SsoSignInCard`:
- Root: `gap-6 md:gap-8 md:short:gap-6 xshort:gap-4 md:xshort:gap-4 … p-6 md:p-12 md:short:p-8 md:xshort:py-6`.
- Title block: `gap-4 xshort:gap-2`. Button + error block: `gap-4 xshort:gap-3`.
- `StaffPortalHeader` and `StaffSsoLoginFooter`: `py-5`/`py-6` → add `xshort:py-3`.

The SSO card has less content than the admin card, so these tiers give more headroom than strictly needed. They are kept anyway, so both pages look identical at the same viewport height. Without them, switching between `/admin/login` and `/staff/login` on the same laptop would show visibly different spacing.

### 3. Background follows the root

The background stays `absolute inset-0` on the root. The root is now exactly viewport height with `overflow-hidden`, so the image covers the viewport and is no longer stretched to the scrolled content height.

## Risks / Trade-offs

- [`overflow-hidden` on the root clips the SSO error toast] → Toasts render in the `fixed` `ToastViewport` at the app root, outside this page's tree. Verify by forcing a failed sign-in (for example by visiting `/staff/login?code=invalid`) and checking that the toast and the inline error are both visible.
- [Header wraps to two lines at narrow widths (`flex-wrap`) and takes extra height] → It is `shrink-0`, so `main` absorbs the difference and scrolls if needed. Covered by the 360×640 scenario.
- [Drift between the two login pages' layouts over time] → This is accepted for now. The follow-up to extract a shared shell would remove it.

## Open Questions

- Follow-up (not blocking): extract a shared `GatewayLoginShell` used by both `/admin/login` and `/staff/login`. This does not change any spec or task in this change.
