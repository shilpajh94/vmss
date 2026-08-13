## 1. Page scaffold

- [x] 1.1 Create `src/presentation/pages/visitor-portal-landing/visitor-portal-landing.tsx`
- [x] 1.2 Create `src/presentation/pages/visitor-portal-landing/Components/PortalHeader.tsx` (logo mark + "VisitorPass" wordmark)
- [x] 1.3 Create `src/presentation/pages/visitor-portal-landing/Components/PortalFooter.tsx` (logo, tagline, Privacy Policy / Terms of Service links, support contact email)

## 2. Hero and action cards

- [x] 2.1 Create `src/presentation/pages/visitor-portal-landing/Components/PortalHero.tsx` ("Welcome to the Visitor Portal" heading + supporting copy)
- [x] 2.2 Create `src/presentation/pages/visitor-portal-landing/Components/ActionCard.tsx` (icon, title, description, button — reused for both entry points)
- [x] 2.3 Compose the two action cards in `visitor-portal-landing.tsx`: "Request a Visit" (filled button, `Link` to `/visitor/request`) and "Track Your Visit" (outlined button, `Link` to `/visitor/track`)

## 3. Routing

- [x] 3.1 Replace the `/` route in `src/App.tsx` to render the new landing page instead of `HomePage`
- [x] 3.2 Delete `src/presentation/pages/home/`

## 4. Verification

- [x] 4.1 Run the app locally and confirm the landing page renders at `/` with header, hero, both action cards, and footer
- [x] 4.2 Confirm clicking each CTA updates the URL to `/visitor/request` or `/visitor/track` respectively (even though no page renders yet)
- [x] 4.3 Confirm no remaining references to the removed `home` page anywhere in `src/`
