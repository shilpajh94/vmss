## Context

After `modernize-visitor-landing-page`, `components/layout/SplitScreenLayout.tsx` hosts `/`, `/admin/login` and `/staff/login`. It takes `portalLabel`, `brand` (headline, tagline, highlights), `footerLinks`, `aside`, `contentClassName` and `children`. It always centres the content and always shows the photo on desktop.

The remaining public screens are built differently:

| Screen | Current shell |
|---|---|
| OTP request, OTP verify, history lookup, history | `PortalHeader` + `OtpScreenLayout` (photo, white round back button, in-photo "Request a Visit" h1) + `PortalFooter`; each screen draws its own white card |
| Wizard | `PortalHeader backTo="/"` + `VisitorRequestWizard` (220px `StepSidebar` rail from `lg`, `StepProgressHeader` below `lg`, white form card with a sticky action bar) + `PortalFooter` |
| Track | `PortalHeader backTo="/"` + photo + in-photo h1 + `TrackingLookupCard`/`StatusPanel`/no-result cards in a wrapping row + `PortalFooter` |
| Not-found, route error | `PortalHeader` + centred text + `PortalFooter` |

Constraints:
- `RouteErrorPage` renders outside every provider, router context included. It can use no `Link` and no context hooks.
- `check-theme-colors.mjs` exempts `pages/visitor-*`, `staff-login`, `staff-sso-login`, but not `pages/not-found` or `components/`. Those must use tokens only.
- `rebrand-to-guestify`'s `brand-identity` delta still carries a "Logo Variant Matches Its Background" requirement that this change supersedes.

## Goals / Non-Goals

**Goals:**
- Every public screen on one shell. No public page keeps `PortalHeader` or `PortalFooter`.
- Zero behaviour change in the OTP, history, wizard, submission and tracking flows. Only presentation moves.

**Non-Goals:**
- Restyling the wizard's step fields themselves (`VisitorFieldsForm`, dynamic fields, uploads, review rows). They already use theme tokens and sit on the white panel unchanged.
- Kiosk or staff-side visitor registration (`staff-visitor-registration`), which lives inside the staff shell.

## Decisions

### D1. Extend `SplitScreenLayout` instead of adding a second shell

New optional props, all defaulting to today's behaviour so the three existing pages render identically:
- `back?: { to: string } | { onClick: () => void }`: renders a round on-dark "Back" control beside the logo in the brand panel and in the top strip. It's a `Link` for `to` and a button for `onClick`. The wizard and the OTP screens pass `onClick`, so the unsaved-changes guard and the OTP state reset keep working through their existing handlers.
- `panel?: ReactNode`: replaces the brand panel's middle block (headline, tagline, highlights). The wizard passes its step list here. When set, the photo isn't rendered either: the panel is plain navy plus the cyan glow, which is calmer behind a step list and saves the photo download on the wizard.
- `panelClassName?: string`: the brand panel width. The default is `w-[45%] xl:w-1/2`; the wizard passes `w-[340px]` so the form keeps most of the width.
- `align?: 'center' | 'start'`: content vertical alignment. Screens with growing content pass `start`: the wizard, history, and track once a result or error shows.

`RouteErrorPage` can't render a `Link`, so it passes no `back`. The logo stays a plain image. Nothing else in the layout needs router context.

*Alternative considered:* a separate `WizardLayout`. Rejected because it would duplicate the strip, footer, scroll container and photo gating, which is what the earlier changes just consolidated.

### D2. One visitor brand module

`components/layout/visitor-brand.tsx` exports:
- `VISITOR_BRAND`, the landing page's current headline, tagline and highlights, moved from `visitor-portal-landing.tsx`;
- `visitorFooterLinks()`: Privacy and Terms through `footerLinks()`, plus "Support Contact" when `SUPPORT_EMAIL` is set.

The landing, OTP, history, track, not-found and error screens all use it, so the brand panel reads identically across the flow (spec: "Visitor screens share one brand copy and footer"). It lives under `components/`, not a page folder, because `not-found/` and the landing page both import it.

### D3. OTP and history screens

`OtpScreenLayout` becomes a thin wrapper:
```
SplitScreenLayout portalLabel="Visitor Portal"
                  brand=VISITOR_BRAND
                  back={{ onClick: onBack }}
```
plus an `align` pass-through (history uses `start`). The in-photo "Request a Visit" title and the white back button go away.

Each screen drops its card box:
- `OtpRequestScreen`, `OtpVerifyScreen`: the `h3` "Request a visit" becomes the shared `AuthFormHeading`-style `h1`. "Request OTP" and "Verify and continue" use `AUTH_PRIMARY_BUTTON_CLASS`. Request and verify errors use `AuthErrorAlert`. The registration-type segmented control and the "code sent" notice keep their markup.
- `ReturnVisitHistoryScreen`: the heading becomes an `h1`. The visit rows keep their bordered list-item style. The "Start a new request" action becomes the cyan primary button.
- The history-lookup skeleton loses its card wrapper.

`AuthFormParts` is reused as is. Its name says "auth" but its parts are generic; renaming it is churn outside this change.

### D4. Wizard

`VisitorRequestPage`'s wizard branch renders:
```
SplitScreenLayout panel={<StepSidebar … onDark />} panelClassName="w-[340px]" align="start" back={{ onClick: () => navigate('/') }}
```
The contents:
- **`StepSidebar`** gets an on-dark style: `sidebar-text` labels, a dimmed `sidebar-muted` for upcoming steps, cyan markers and connector fill on `sidebar-line` tracks. It keeps its `lg:flex` visibility and completed-step selection.
- **The form panel** is wider: `contentClassName="max-w-[760px]"`, and the portal tag row is hidden for the wizard through the same prop.
- **The step content** renders directly on the panel surface. The white card border is removed, and the step heading stays where each step draws it.
- **The action bar** stays `sticky bottom-0` inside the scroll panel at every width. "Next" keeps the cyan fill and "← Back" becomes the outlined neutral button.
- **`StepProgressHeader`** keeps its markup below `lg`, and its card loses the border to match the panel.

`navigate('/')` goes through React Router, so `useUnsavedChangesGuard`'s blocker still intercepts it.

### D5. Track page

The page is `SplitScreenLayout` with `VISITOR_BRAND`, `back={{ to: '/' }}`, `contentClassName="max-w-[520px]"`, and `align` set to `start` once `status !== 'idle'`. The children are:
- `TrackingLookupCard` without its box: an `h1` "Enter Your Tracking ID", the existing description, the field, and the "Track Request" cyan button;
- the loading skeleton;
- `StatusPanel`, which keeps a bordered panel because it is a result object rather than a form, with its shadow softened;
- the no-result state as `AuthErrorAlert` with the title "No Result".

The old in-photo "Track Your Visit" title is dropped. The brand panel keeps the shared visitor copy (D2), and the form's `h1` is the page heading.

### D6. Not-found and route error

Both pages use `SplitScreenLayout` with `VISITOR_BRAND` and `visitorFooterLinks()`. The content is:
- the "404" overline (not-found only);
- the `h1` ("Page not found" / "Something went wrong");
- the text;
- a cyan primary action.

`RouteErrorPage` keeps `role="alert"` and `useForceLightTheme()`, and its button keeps the "Reload" name.

### D7. Delete `PortalHeader` and `PortalFooter`

After D3–D6 nothing imports them. Delete both. `BrandLogo`'s `themed` variant stays: `AppShell`'s phone bar uses it.

### D8. Spec overlaps with other active changes

- **`modernize-visitor-landing-page`** (not yet archived) owns `SplitScreenLayout` and the previous edit of "The Public Portal Footer Is Compact". Archive it first. This change's footer delta includes its "Track page footer" scenario, so either archive order passes validation.
- **`rebrand-to-guestify`:** delete the "Logo Variant Matches Its Background" requirement from its `brand-identity` delta, and note in its proposal that this change carries it. This is the same resolution used twice before.

## Risks / Trade-offs

- [The wizard's unsaved-changes guard must still fire when Back is used from the navy panel.] → Back uses `navigate('/')` (D4), and a manual check confirms the confirmation dialog appears.
- [The sticky action bar inside a scroll container behaves differently from today's page-level scroll.] → `sticky bottom-0` works relative to the nearest scrolling ancestor, which is now the content panel. Verify at 1440×700 and 375×667 with a long step (Visitor Info).
- [The route error page can't use router context.] → The layout has no router dependency when `back` is unset (D1). `test_error_page_renders_light_in_dark_mode` exercises it.
- [e2e assertions tied to the old chrome.]
  - `test_error_page_renders_light_in_dark_mode` expects a header and footer with the dark-wordmark logo; update it to the brand panel's single on-dark logo, which matches the modified theme-mode scenario;
  - `test_public_footer_is_compact` measures the old footer's logo, tagline and copyright; update it to the split-screen footer's height, padding and overflow;
  - the visitor flows select by label and button name, which are unchanged.
- [A large surface for one change.] → The tasks are grouped by screen, and each group is verifiable on its own (screenshots plus targeted e2e).

## Migration Plan

This is a frontend-only change. Ship with the next web release; roll back by reverting the commit. No API or configuration changes.
