## RENAMED Requirements

- FROM: `### Requirement: The Portal Presents the Visimio Brand Everywhere`
- TO: `### Requirement: The Portal Presents the Guestify Brand Everywhere`

- FROM: `### Requirement: Copyright Line Names Visimio and the Current Year`
- TO: `### Requirement: Copyright Line Names Guestify and the Current Year`

## MODIFIED Requirements

### Requirement: The Portal Presents the Guestify Brand Everywhere
The portal SHALL identify the product as "Guestify" on every surface that
shows a product name or mark:
- admin, staff and reception sidebars;
- the phone/tablet navigation bar;
- the visitor portal header and footer;
- the staff login and SSO login headers and footers;
- the browser tab title;
- the favicon;
- the push-notification fallback title.

The retired names "VisitorPass" and "Visimio", the old placeholder "V"
tile and the Visimio "V" mark SHALL NOT appear anywhere in the rendered
portal.

#### Scenario: Sidebar shows the Visimio logo
- **WHEN** a signed-in admin opens any admin page
- **THEN** the sidebar header shows the Guestify logo (the teal "G" pin
  mark, teal "Gu" and white "estify") with alt text "Guestify", and
  neither "VisitorPass" nor "Visimio" text is present

#### Scenario: Collapsed sidebar shows the Guestify mark
- **WHEN** a signed-in admin collapses the sidebar
- **THEN** the sidebar header shows only the teal "G" pin mark

#### Scenario: Browser tab identifies the product
- **WHEN** any route is opened
- **THEN** the document title reads "Guestify" and the favicon shows the
  Guestify "G" pin mark

#### Scenario: Push notification without a title
- **WHEN** a background push notification arrives with no title in its
  payload
- **THEN** the system notification is titled "Guestify"

#### Scenario: Retired name cannot return
- **WHEN** a source file under the shipped code roots contains "Visimio"
  or "VisitorPass"
- **THEN** the lint step fails and names the offending file and line

### Requirement: Copyright Line Names Guestify and the Current Year`

## MODIFIED Requirements

### Requirement: The Portal Presents the Guestify Brand Everywhere
The portal SHALL identify the product as "Guestify" on every surface that
shows a product name or mark:
- admin, staff and reception sidebars;
- the phone/tablet navigation bar;
- the visitor portal header and footer;
- the staff login and SSO login headers and footers;
- the browser tab title;
- the favicon;
- the push-notification fallback title.

The retired names "VisitorPass" and "Visimio", the old placeholder "V"
tile and the Visimio "V" mark SHALL NOT appear anywhere in the rendered
portal.

#### Scenario: Sidebar shows the Visimio logo
- **WHEN** a signed-in admin opens any admin page
- **THEN** the sidebar header shows the Guestify logo (the teal "G" pin
  mark, teal "Gu" and white "estify") with alt text "Guestify", and
  neither "VisitorPass" nor "Visimio" text is present

#### Scenario: Collapsed sidebar shows the Guestify mark
- **WHEN** a signed-in admin collapses the sidebar
- **THEN** the sidebar header shows only the teal "G" pin mark

#### Scenario: Browser tab identifies the product
- **WHEN** any route is opened
- **THEN** the document title reads "Guestify" and the favicon shows the
  Guestify "G" pin mark

#### Scenario: Push notification without a title
- **WHEN** a background push notification arrives with no title in its
  payload
- **THEN** the system notification is titled "Guestify"

#### Scenario: Retired name cannot return
- **WHEN** a source file under the shipped code roots contains "Visimio"
  or "VisitorPass"
- **THEN** the lint step fails and names the offending file and line

### Requirement: Logo Variant Matches Its Background
The portal SHALL use the logo variant that stays legible on the surface
behind it:
- the lockup with the dark navy "estify" on light surfaces (visitor portal
  header and footer, phone/tablet navigation bar);
- the lockup with the white "estify" on dark surfaces (sidebars and staff
  login headers);
- the "G" pin mark alone where there is no room for the wordmark.

In every lockup variant the mark and the "Gu" letters SHALL stay teal.
Each logo SHALL keep its aspect ratio, SHALL render sharply on 2× displays,
and SHALL have a transparent background (no navy box visible on a light
surface).

#### Scenario: Dark surface uses the on-dark logo
- **WHEN** the staff login header (navy background) renders
- **THEN** it shows the Guestify logo variant whose "estify" is white, not
  the dark-wordmark variant

#### Scenario: Light surface uses the standard logo
- **WHEN** the visitor portal header (white background) renders
- **THEN** it shows the Guestify logo with dark navy "estify" and teal
  "Gu", with no background box around it

### Requirement: Copyright Line Names Guestify and the Current Year
Every footer that carries a copyright line SHALL read "© {current year}
Guestify. All rights reserved.", with the year taken from the viewer's
clock at render time, not hard-coded.

#### Scenario: Staff login footer copyright
- **WHEN** the staff login screen renders in 2027
- **THEN** its footer reads "© 2027 Guestify. All rights reserved."

### Requirement: Logo Images Are Accessible
Every rendered logo image SHALL have alt text "Guestify". Where the logo
acts as a home link, the link SHALL expose the accessible name "Guestify
home". A logo that is purely decorative next to visible "Guestify" text
SHALL have empty alt text.

#### Scenario: Header logo link
- **WHEN** a screen-reader user focuses the logo link in the visitor portal
  header
- **THEN** it is announced as "Guestify home"

### Requirement: The Logo Keeps Its Aspect Ratio in Any Container
Every rendered Guestify logo SHALL keep the aspect ratio of its source
image, and SHALL render no wider than its natural width at the requested
height. This SHALL hold regardless of its container's flex, grid or
stretch alignment. No logo slot SHALL overflow or overlap neighbouring
content at 375px, 768px or 1440px viewport widths.

#### Scenario: Footer logo is not stretched
- **WHEN** the visitor portal footer renders at 375px or 1440px
- **THEN** the footer logo is 28px tall, and its width is 28px times the
  light lockup's intrinsic aspect ratio (±2px), not stretched to the width
  of the footer column

#### Scenario: Wider wordmark fits the expanded sidebar
- **WHEN** the expanded sidebar renders at 1440px
- **THEN** the on-dark lockup sits fully inside the sidebar header with
  no clipping, and the collapse control stays visible
