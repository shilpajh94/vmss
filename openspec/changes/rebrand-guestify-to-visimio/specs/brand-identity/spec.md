## MODIFIED Requirements

### Requirement: The Portal Presents the Visimio Brand Everywhere
The portal SHALL identify the product as "Visimio" on every surface that
shows a product name or mark:
- admin, staff and reception sidebars;
- the phone/tablet navigation bar;
- the visitor portal header and footer;
- the staff login and SSO login headers and footers;
- the browser tab title;
- the favicon and touch icon;
- the push-notification fallback title.

The retired names "VisitorPass" and "Guestify", the old placeholder "V"
tile and the Guestify "G" pin mark SHALL NOT appear anywhere in the
rendered portal. Logo asset files SHALL be named `logo-visimio*`.

#### Scenario: Sidebar shows the Visimio logo
- **WHEN** a signed-in admin opens any admin page
- **THEN** the sidebar header shows the Visimio logo (mark plus white
  wordmark) with alt text "Visimio", and neither "VisitorPass" nor
  "Guestify" text is present

#### Scenario: Browser tab identifies the product
- **WHEN** any route is opened
- **THEN** the document title reads "Visimio" and the favicon and touch
  icon show the Visimio mark

#### Scenario: Push notification without a title
- **WHEN** a background push notification arrives with no title in its
  payload
- **THEN** the system notification is titled "Visimio"

#### Scenario: Retired name is blocked in code
- **WHEN** "VisitorPass" or "Guestify" (any case) appears under `src`,
  `public` or `index.html`
- **THEN** `npm run lint` fails and names the offending file and line
