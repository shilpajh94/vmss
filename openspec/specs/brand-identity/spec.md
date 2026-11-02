# brand-identity Specification

## Purpose
Defines how the portal presents the Visimio product identity: its name,
logo variants, favicon, document title and copyright line. All of them
come from one brand source, so a future rename is a one-place change.

## Requirements

### Requirement: The Portal Presents the Visimio Brand Everywhere
The portal SHALL identify the product as "Visimio" on every surface that
shows a product name or mark:
- admin, staff and reception sidebars;
- the phone/tablet navigation bar;
- the visitor portal header and footer;
- the staff login and SSO login headers and footers;
- the browser tab title;
- the favicon;
- the push-notification fallback title.

The text "VisitorPass" and the old placeholder "V" tile SHALL NOT appear
anywhere in the rendered portal.

#### Scenario: Sidebar shows the Visimio logo
- **WHEN** a signed-in admin opens any admin page
- **THEN** the sidebar header shows the Visimio logo (mark plus white
  wordmark) with alt text "Visimio", and no "VisitorPass" text is present

#### Scenario: Browser tab identifies the product
- **WHEN** any route is opened
- **THEN** the document title reads "Visimio" and the favicon shows the
  Visimio mark

#### Scenario: Push notification without a title
- **WHEN** a background push notification arrives with no title in its
  payload
- **THEN** the system notification is titled "Visimio"

### Requirement: Logo Variant Matches Its Background
The portal SHALL use the logo variant that stays legible on the surface
behind it:
- the lockup with the dark wordmark on light surfaces (visitor portal
  header and footer);
- the lockup with the white wordmark on dark surfaces (sidebars and staff
  login headers);
- the mark alone where there is no room for the wordmark.

Each logo SHALL keep its aspect ratio and SHALL render sharply on 2×
displays.

#### Scenario: Dark surface uses the on-dark logo
- **WHEN** the staff login header (navy background) renders
- **THEN** it shows the Visimio logo variant whose wordmark is white, not
  the dark-wordmark variant

#### Scenario: Light surface uses the standard logo
- **WHEN** the visitor portal header (white background) renders
- **THEN** it shows the Visimio logo with the dark wordmark

### Requirement: Copyright Line Names Visimio and the Current Year
Every footer that carries a copyright line SHALL read "© {current year}
Visimio. All rights reserved.", with the year taken from the viewer's
clock at render time, not hard-coded.

#### Scenario: Staff login footer copyright
- **WHEN** the staff login screen renders in 2027
- **THEN** its footer reads "© 2027 Visimio. All rights reserved."

### Requirement: Logo Images Are Accessible
Every rendered logo image SHALL have alt text "Visimio". Where the logo
acts as a home link, the link SHALL expose the accessible name "Visimio
home". A logo that is purely decorative next to visible "Visimio" text
SHALL have empty alt text.

#### Scenario: Header logo link
- **WHEN** a screen-reader user focuses the logo link in the visitor portal
  header
- **THEN** it is announced as "Visimio home"

### Requirement: The Logo Keeps Its Aspect Ratio in Any Container
Every rendered Visimio logo SHALL keep the aspect ratio of its source
image, and SHALL render no wider than its natural width at the requested
height. This SHALL hold regardless of its container's flex, grid or
stretch alignment.

#### Scenario: Footer logo is not stretched
- **WHEN** the visitor portal footer renders at 375px or 1440px
- **THEN** the footer logo is 28px tall and about 131px wide (its natural
  ratio), not stretched to the width of the footer column

### Requirement: The Logo Stays Legible in the Dark Theme
Every rendered logo SHALL show its complete wordmark against the surface
behind it, in both the light and the dark theme. A logo that uses the
dark-wordmark lockup on a surface that follows the theme SHALL show the
white-wordmark lockup while the dark theme is active, and the
dark-wordmark lockup while the light theme is active. The swap SHALL keep
the logo's size, position, aspect ratio and alt text, and SHALL follow a
live theme switch without a reload.

#### Scenario: Themed surface in dark mode
- **WHEN** a logo on a surface that follows the theme renders while the
  dark theme is active
- **THEN** it shows the full product wordmark in white, not only the teal
  leading letters

#### Scenario: Public pages are unaffected
- **WHEN** a visitor opens the visitor portal, or the route error page is
  shown, on a device set to dark
- **THEN** the header and footer show the dark-wordmark lockup, because
  public pages always render light
