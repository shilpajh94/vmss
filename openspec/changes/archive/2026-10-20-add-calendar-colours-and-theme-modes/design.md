## Context

See proposal.md for motivation. Current state that shapes the approach:

- **Tokens.** Colours are Tailwind v4 `@theme` tokens in
  `src/styles/theme.css` (`--color-surface`, `--color-text`,
  `--color-admin-accent`, …). Components use them through generated
  utilities (`bg-surface`, `text-text-muted`, `bg-info/10`), about 1,680
  uses.
- **Hard-coded colours.** About 30 files hard-code colours: about 45
  arbitrary hex classes (`bg-[#f8fafc]`, `border-[#cbd5e1]`,
  `text-[#475569]`, …) and about 8 `bg-white`. There are 91 `text-white`
  uses. Most sit on solid accent, status or primary fills.
- **Dual-use tokens.** Accent and status tokens are used both as solid
  fills under white text (admin-accent 53×, secondary-accent 24×) and as
  coloured text on the surface. A dark theme can't just lighten them
  without breaking white-on-fill contrast.
- **Sidebars** are already a fixed dark navy (hex classes inside
  `AdminSidebar`/`DashboardSidebar`/`ReceptionSidebar`/`SidebarHeader`).
- **Charts.** `components/dashboard/chart-theme.ts` resolves token values
  once per mount (`useMemo([])`), so charts would not follow a live switch.
- **Layouts.** Signed-in pages render under `AdminLayout` or
  `StaffLayout`. Every public page, including both login pages, renders
  under `PublicLayout`.
- **Calendar.** Calendar chips (`pages/calendar/components/*`) are white
  with a 6px status dot in month view and a small label pill in week view.
  `calendar-status.ts` already maps each status to `toneClass`/`dotClass`.
- **Storage.** `hooks/use-stored-state.ts` already wraps `localStorage`
  with try/catch.

## Goals / Non-Goals

**Goals:**
- Status-filled calendar events that read at a glance in both themes.
- A Light / Dark / System choice for staff and admin pages, applied before
  first paint, stored per browser.
- A light theme that is pixel-identical to today.

**Non-Goals:**
- Theming public visitor pages or the login pages.
- Storing the choice on the user account.
- Redesigning the sidebar, which stays dark navy in both themes.
- Per-tenant brand colours.

## Decisions

### D1. Theme = token overrides on `<html data-theme="dark">`

`theme.css` gains a `:root[data-theme="dark"] { --color-…: … }` block
that redefines every semantic token to the values in the design-theme
spec. It also sets `color-scheme: dark` on that selector, and
`color-scheme: light` on `:root`.

Because every utility reads `var(--color-…)`, about 1,680 token uses switch
with zero component edits.

A Tailwind v4 custom variant
`@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));`
is added for the rare case that genuinely needs a different class in dark
(for example a shadow). Prefer tokens over `dark:` everywhere else.

*Alternative:* `.dark` class plus `dark:` variants on every component.
Rejected: it would touch hundreds of class lists, and the token layer
already exists.

### D2. `on-primary` / `on-accent` tokens for text on solid fills

New tokens: `--color-on-primary` and `--color-on-accent`.

| Theme | Value |
|---|---|
| Light | `#FFFFFF`, identical to today's `text-white` |
| Dark | `#0F172A` |

In dark, accents and status tokens are lifted to their 400-level shades
for readable coloured text on the dark surface. Dark text on those fills
then keeps ≥4.5:1 (for example `#0F172A` on `#2DD4BF` ≈ 9.8:1).

Migration: every `text-white` on a `bg-admin-accent`, `bg-secondary-accent`,
`bg-success`, `bg-warning`, `bg-danger`, `bg-info`, `bg-vip` or
`bg-primary` fill becomes `text-on-accent` / `text-on-primary`.

- A `text-white` sitting on the sidebar's fixed navy, or on an image,
  stays `text-white`.
- An audit script lists the remaining `text-white` with their nearest
  `bg-*` for review (task 3.1).

*Alternative:* keep the accent and status hues the same in both themes.
Rejected: `#0B8B84` text on `#0F172A` is about 4.0:1 and `#3B82F6` about
4.1:1, both below AA, and status text is used 130+ times.

### D3. Hard-coded colours → tokens (light-identical mapping)

Map each light hex to the existing token with the same value (or the
nearest one):

| Hard-coded | Token |
|---|---|
| `#f8fafc`, `#f1f5f9` | `bg-border-subtle` |
| `#cbd5e1` | `border-border` |
| `#475569`, `#334155` | `text-text-muted` |
| `bg-white` | `bg-surface` |

Tinted hexes (`#ecfeff`, `#f0fdfa`, `#dbeafe`, `#fee2e2`, `#fef3c7`, and
`#991b1b`/`#92400e`/`#1e40af` text) become `bg-<token>/10` with
`text-<token>`.

Where the mapped token differs visibly in light (for example `#475569` vs
`text-muted`'s `#64748B`), add a token rather than shift light: introduce
`--color-text-secondary` (`#475569` light, `#CBD5E1` dark).

- **Exempt:** the three sidebars and `SidebarHeader` keep their navy hexes,
  marked with a `theme-fixed` comment on the line.
- **Lint:** add `scripts/check-theme-colors.mjs`, chained into
  `npm run lint` like `check-brand.mjs`. It fails on any new arbitrary
  hex colour class or `bg-white`/`bg-black` under `src/presentation`
  unless the line has `theme-fixed`. That stops the dark theme from
  regressing silently.

### D4. Mode state: `ThemeModeProvider`, applied only inside signed-in layouts

- `presentation/context/theme-mode-context.tsx`:
  - holds `mode: 'light' | 'dark' | 'system'`;
  - stored under `localStorage['vmss.themeMode']` via `use-stored-state`;
  - an invalid or missing value falls back to `'system'`;
  - `resolved: 'light' | 'dark'` comes from a
    `matchMedia('(prefers-color-scheme: dark)')` subscription
    (`useSyncExternalStore`, same pattern as `use-media-query.ts`).
- The provider wraps the app (in `App.tsx`, near the other providers),
  but **applying** the theme is scoped:
  - `AdminLayout` and `StaffLayout` call `useApplyTheme()`, which sets
    `document.documentElement.dataset.theme = resolved`;
  - `PublicLayout` calls `useApplyTheme('light')`, which removes it.
  - Layout effects run on route change, so moving between a public and a
    signed-in page flips correctly.
- Cross-tab: listen to the `storage` event, so a choice in one tab updates
  the others.

### D5. No flash: inline pre-paint script in `index.html`

A tiny classic `<script>` in `<head>`, before the CSS and the module
script:

1. Reads `localStorage['vmss.themeMode']` (in a try/catch).
2. Resolves `system` via `matchMedia`.
3. Sets `data-theme="dark"` on `<html>` only when the path starts with
   `/admin/`, `/staff/` or `/reception/` and is not a login page
   (`/admin/login`, `/staff/login`, `/staff/sso…`).

It duplicates the scoping rule from D4 by necessity; a comment in both
places points at the other. It also updates `<meta name="theme-color">`
to the dark surface colour.

*Alternative:* apply in React only. Rejected: it gives a visible white
flash before hydration on every reload.

### D6. Theme control: `ThemeModeMenu` in `AppTopBar`

- A round icon button matching the refresh control (`size-10 lg:size-8`),
  placed between refresh and the bell.
- The icon reflects the current mode: sun, moon, or monitor for System.
  Add `SunIcon`, `MoonIcon` and `MonitorIcon`-style glyphs to `icons.tsx`
  if missing.
- Opens a small popover menu, implemented as `role="menu"` with
  `menuitemradio` + `aria-checked`, using the existing `usePresence` and
  `ui-motion` popover timing:
  - arrow keys move between items, and Enter/Space selects;
  - Escape closes it and returns focus;
  - an outside click closes it.
- It stays visible at phone width, as an icon only (app-shell
  modification).

### D7. Charts re-resolve on theme change

`useChartTheme()` adds the resolved theme to its memo dependencies (read
from `useThemeMode()`), so Recharts props get new concrete colours.

The three series tokens (`--color-chart-*`) get dark values validated
against `#0F172A` with the same CVD check used originally:

| Series | Dark value |
|---|---|
| scheduled | `#4C97EC` |
| checked-in | `#2CC58C` |
| no-show | `#F07A4A` |

Record the check result in the implementation.

### D8. Calendar status fills

`calendar-status.ts` adds per status:

- `fillClass`: background `bg-<token>/15`, with `dark:bg-<token>/25`
  because a 15% tint on navy is too faint. Visited uses
  `bg-neutral-subtle`.
- `dotClass`: the existing solid `bg-<token>` marker.

**Text on the fill is body text (`text-text`), not the status colour.**
*Revised during apply:* the original plan put `text-<token>` on the tint.
Measured, that is 1.9–3.1:1 in light and 4.4:1 for info and danger in
dark, which fails the spec's 4.5:1. Muted text on the fills is 3.9–4.4:1,
so chips use `text-text` throughout and set the time apart by weight.
Status is still carried three ways: the fill colour, the solid status
dot, and the status word (visible in week and day views, and in the
accessible name everywhere).

Chip variants:

- **compact (month):** a full-width filled pill with a 3px category left
  accent, a status dot, and truncated `time · name`.
- **block (week):** a filled card with a dot plus the status word.
- **detail (day):** a filled card with a dot plus the status word.

Busy-day tint on the month count badge, via a `busyTint(total)` helper.
Text is `text-text` at every step.

| Day total | Tint |
|---|---|
| 0 | hidden |
| 1–4 | `bg-admin-accent/10` |
| 5–14 | `bg-admin-accent/25` |
| ≥15 | `bg-admin-accent/45` |

*Revised:* a solid accent with white text was 4.2:1 in light, so the
strong step became a 45% tint.

The phone count badge uses the same helper, so it shows on phones too. The
filter chips reuse `fillClass` and the dot when on. Their "off" style
(struck through, neutral) is unchanged, so they double as the legend.

**Measured contrast** (WCAG, text against the tint composited over
`surface`):

| Fill | Light (`#0F172A` on /15) | Dark (`#F1F5F9` on /25) |
|---|---|---|
| Pending (info) | 15.0 | 10.3 |
| Expected (success) | 15.4 | 9.6 |
| Inside (secondary-accent) | 15.5 | 9.3 |
| Missed (warning) | 15.9 | 9.2 |
| Denied (danger) | 14.7 | 11.1 |
| Visited (neutral-subtle) | 14.4 | 9.5 |
| Busy /10, /25, /45 | 15.7 / 13.0 / 9.8 | 13.5 / 9.5 / 5.6 |

## Risks / Trade-offs

- **A missed hard-coded colour shows as a white panel in dark.**
  → The `check-theme-colors` lint, plus the e2e dark-mode screenshot sweep
  of every staff and admin route (task 6), plus manual review.
- **`text-white` → `on-accent` conversion mistakes** (for example text on
  the sidebar becoming dark). → Convert only where the same element or its
  direct parent has a solid accent/status/primary `bg-*`; sidebars are
  exempt; the audit list is reviewed by hand.
- **The pre-paint script and React disagree on scope** (flash on login).
  → One shared path rule, documented in both places; an e2e test asserts
  that `/staff/login` has no `data-theme` with Dark stored.
- **Third-party UI** (Recharts tooltips, native `<select>` popups) may
  ignore tokens. → Recharts gets explicit colours (D7); `color-scheme`
  themes native popups.
- **Light theme drift.** → D2/D3 mappings are value-identical in light. A
  before/after light screenshot comparison of key pages is part of
  verification.

## Migration Plan

Web-only and client-side. Existing users get System by default, so users
on dark devices will see the dark theme on their next load. That is the
intended behaviour of "System", and it is called out in the release note.
Rollback: revert the change. The stored key is ignored once the provider
is gone.

## Open Questions

- Should the visitor-facing pages get the theme later? That would be a
  separate change; the scoping rule in D4/D5 is where it would be lifted.
