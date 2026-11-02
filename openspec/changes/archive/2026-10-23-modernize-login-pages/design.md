## Context

`/admin/login` (`staff-login/`) and `/staff/login` (`staff-sso-login/`) each build their own copy of the same shell:
- the lobby photo (`HeroImage`) under a `bg-primary/55` overlay;
- a navy header (`StaffGatewayHeader` / `StaffPortalHeader`, identical except for the badge text);
- a centred card;
- a footer (`StaffLoginFooter` / `StaffSsoLoginFooter`, byte-identical).

The viewport-fit behaviour depends on `h-dvh` + `overflow-hidden` on the root and on `min-h-0 flex-1 overflow-y-auto` on `main`. It also uses the custom `short` (≤900px) and `xshort` (≤800px) height variants in `src/styles/index.css`.

Both pages are always light (theme-mode "Public pages always render in the light theme"). `scripts/check-theme-colors.mjs` exempts the two page directories, but not `src/presentation/components/`.

The active `rebrand-to-guestify` change also modifies `staff-login`'s "visually distinct" requirement (all its tasks are done except the e2e run). This change's delta builds on that Guestify wording.

## Goals / Non-Goals

**Goals:**
- One shared layout, so the admin and staff pages can't drift apart visually again.
- Keep the existing sign-in hooks (`use-staff-login-page.ts`, `use-staff-sso-login-page.ts`) untouched. This is a presentation-only change.
- Keep every accessible name the e2e suite selects on.

**Non-Goals:**
- Dark-mode sign-in pages. They stay always-light.
- Changing whether the admin page offers SSO. The current code shows an "or / Sign in with SSO" option under the password form. That stays as it is.
- New images or a new illustration. The existing lobby photo assets are reused, so the public-page download budget is unaffected.
- Visitor portal pages.

## Decisions

### D1. A shared `AuthSplitLayout` in `src/presentation/components/auth/`

The layout takes a `portalLabel` ("Admin Portal" / "Staff Portal") and `children` (the form content). It renders:
- the brand panel, or the narrow-screen strip;
- the scrollable form panel;
- the help line and footer links at the bottom of the form panel.

The pages shrink to "hook + `<AuthSplitLayout>` + card". The four header/footer components are deleted.

*Alternative considered:* restyle each page in place. Rejected because it doubles every future tweak, and the duplicate header/footer files are the reason the two pages already differ only by a string.

### D2. Layout mechanics

Root: `flex h-dvh overflow-hidden`.

At `lg` (1024px) and wider:
- the brand panel is `hidden lg:flex lg:w-[45%] xl:w-1/2`, relative, with `HeroImage` absolutely filling it. Over the photo sit a navy gradient (`from-primary/95 via-primary/80 to-primary/60`) and a faint cyan radial glow;
- the form panel is `flex-1 min-h-0 overflow-y-auto bg-surface`. Inside it, a `min-h-full flex flex-col` wrapper centres the form block (`max-w-[400px]`) vertically and pushes the footer to the bottom with `mt-auto`.

This keeps the proven "only the content region scrolls" pattern from `fb5ed22`. The brand panel never scrolls.

Below `lg`, the root becomes `flex-col`. A `lg:hidden` navy strip at the top holds the on-dark logo and the portal tag (`shrink-0`). The form panel takes the remaining height and scrolls.

The brand panel loads `HeroImage` only inside the `lg` panel, so phones no longer download the photo at all. The `<picture>` stays in the DOM under `hidden`, and `display:none` images inside `<picture>` are still fetched by some browsers. So the panel renders `HeroImage` only when `matchMedia('(min-width: 1024px)')` matches, using a small hook with a resize listener. The narrow strip is a solid gradient.

### D3. Brand panel content is static copy in the layout

The panel shows, top to bottom:
- logo;
- headline ("Every visitor, welcomed securely.");
- tagline;
- three highlights with inline SVG icons: pre-registration and invitations, fast QR check-in, live "who's inside" view;
- copyright line (`copyrightLine()`) pinned to the bottom.

The copy lives in the layout component, not `brand.ts`. It is marketing copy for one surface, not identity. Icons are inline SVGs, matching the existing inline shield in `LoginFormCard`, so no icon library is added.

### D4. Form panel styling

- Portal tag pill (existing `secondary-accent-soft` style).
- `font-display` heading "Welcome back" at 30px, with a muted 14px description.
- Inputs use `TextField` with taller fields (`py-3`) through a className pass-through.
- A full-width primary button with a hover lift and the existing `PendingButton` pending state.
- The SSO button is outlined.
- The divider and security note keep their current wording.
- The error is a `danger`-tinted alert box with an icon and `role="alert"`.

Only theme tokens are used (`primary`, `secondary-accent`, `surface`, `border`, `text-*`, `sidebar-*`, `danger`). As a result, `check-theme-colors.mjs` passes for the new `components/auth/` file without an exemption.

### D5. Password toggle via an optional `TextField` adornment

`TextField` gains an optional `trailing?: ReactNode`. When it is set:
- the input is wrapped in a `relative` div;
- the input gets right padding;
- the adornment is placed at the right edge.

`LoginFormCard` keeps a local `showPassword` state. It passes `type={showPassword ? 'text' : 'password'}` and a `type="button"` toggle with `aria-label` "Show password" / "Hide password" and `aria-pressed`. The label and `useId` wiring are unchanged, so `get_by_label("Password")` still resolves to the input.

*Alternative considered:* a dedicated `PasswordField`. Rejected for now because there is only one caller. The adornment slot is the smaller change and stays reusable.

### D6. Entrance motion

The form block (`.auth-form-enter` in `index.css`) reuses the existing `route-fade-in` keyframes (fade plus a 4px rise) with `--motion-slow` and `--ease-motion-out`. The global reduced-motion rule in `index.css` already reduces this to an instant final state. No new timing values are added.

## Risks / Trade-offs

- [Playwright's `get_by_label("Password")` is a substring match, so it also hits the "Show password" toggle.] → The two e2e `fill()` calls use `get_by_role("textbox", name="Password")` instead. The toggle keeps the standard accessible name.
- [The e2e suite selects "Sign In" with `exact=True`, while the help link reads "Contact System Administrator".] → The button text, field labels and SSO button name are kept verbatim, and the heading change ("Enterprise Sign In" → "Welcome back") is not referenced by any test (checked with grep). Run `test_auth_and_dashboards.py`, `test_toasts.py` and `test_theme_mode.py`.
- [The form must stay visible without scrolling at 1024×700, under the new vertical rhythm.] → Reuse the `short`/`xshort` variants to tighten gaps and the heading size. Verify at 1920×870, 1024×700, 1280×560, 800×500 and 360×640 with the screenshot script or a manual Playwright pass.
- [The `matchMedia` gate makes the brand panel's photo appear after hydration on desktop.] → The gradient paints immediately and the photo fades in. The photo is decorative, so a flash of gradient is acceptable. It also keeps the 15 kB phone budget win.
- [Merge overlap with `rebrand-to-guestify`'s delta on the same requirement.] → Archive `rebrand-to-guestify` before this change. This delta's text already contains the Guestify wording, so archiving in either order yields the right final spec.

## Migration Plan

This is a frontend-only, no-data change. Deploy with the next web release; roll back by reverting the commit. No API or configuration changes.
