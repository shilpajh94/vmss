## Purpose

Keeps the web app fast to load, especially the public visitor pages that
visitors open on phones over mobile data, by bounding what each route
downloads and deferring code that only signed-in staff need.

## ADDED Requirements

### Requirement: Route Groups Are Loaded on Demand
Admin pages, staff pages, the form builder and the registration wizards
SHALL each be split into chunks loaded only when one of their routes is
first visited. Opening a public page SHALL NOT download the code for any
admin or staff page. While a chunk loads, the layout's existing transition
and skeleton SHALL be shown; the page SHALL never be blank.

#### Scenario: Visitor opens the landing page
- **WHEN** a visitor opens `/`
- **THEN** no admin, staff or form-builder page code is downloaded

#### Scenario: First visit to an admin page
- **WHEN** a signed-in admin navigates to an admin page for the first time
  in the session
- **THEN** a skeleton or transition is shown until its chunk has loaded,
  and the page then renders normally

### Requirement: The Push-Notification SDK Is Loaded Only for Signed-In Staff
The push-messaging SDK SHALL NOT be part of the initial bundle. It SHALL be
loaded only after a staff session exists and push is supported and
permitted.

#### Scenario: Public page without a session
- **WHEN** a visitor with no staff session opens any public page
- **THEN** the push-messaging SDK is not downloaded

### Requirement: Public Pages Stay Within a Download Budget
The JavaScript downloaded to render the public landing page SHALL stay
at or below 350 KB gzipped. The hero image SHALL be served in a modern
compressed format with a fallback, sized for the viewport, and marked as
high priority. A build that exceeds the budget SHALL be reported by the
build check.

#### Scenario: Budget check on build
- **WHEN** the production build is produced
- **THEN** the landing page's initial JavaScript is at or below 350 KB
  gzipped, or the check fails and names the size

#### Scenario: Hero image on a phone
- **WHEN** a phone browser that supports AVIF or WebP opens the landing
  page
- **THEN** it downloads the compressed hero variant, not the original PNG
