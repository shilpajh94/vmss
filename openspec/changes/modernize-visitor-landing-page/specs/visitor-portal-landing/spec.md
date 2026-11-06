## MODIFIED Requirements

### Requirement: Landing page presents both visitor entry points
The system SHALL render, at the portal's landing screen, one call-to-action to request a visit and one call-to-action to track an existing visit request. Each SHALL be visually distinct and independently actionable.

Each entry point SHALL be a card showing:
- an icon;
- a title ("Request a Visit" / "Track Your Visit");
- a one-line description;
- a call-to-action label ("Request Visit" / "Track Request").

The whole card SHALL be one link to its route, so a click anywhere on the card navigates. The request card SHALL be styled as the primary choice. The track card SHALL be styled as the secondary choice.

#### Scenario: Both entry points are visible
- **WHEN** a visitor loads the landing page
- **THEN** a "Request a Visit" action and a "Track Your Visit" action are both rendered and visible without further interaction

#### Scenario: Request entry point navigates to the request flow
- **WHEN** a visitor activates the "Request Visit" action
- **THEN** the system navigates to the visit-request route

#### Scenario: Track entry point navigates to the tracking flow
- **WHEN** a visitor activates the "Track Request" action
- **THEN** the system navigates to the visit-tracking route

#### Scenario: Clicking anywhere on a card navigates
- **WHEN** a visitor clicks the description text of the "Track Your Visit" card
- **THEN** the system navigates to the visit-tracking route

#### Scenario: Cards are keyboard reachable
- **WHEN** a keyboard user tabs through the landing page
- **THEN** each card receives focus once, shows a visible focus ring, and activates with Enter

### Requirement: Landing page identifies the product and provides support/legal links
The system SHALL display the product name and a way to reach support or legal information on the landing page.

The Visimio logo SHALL appear in:
- the brand panel, from 1024px wide;
- the top strip, below 1024px wide.

The copyright line "© {current year} Visimio. All rights reserved." SHALL appear in the brand panel from 1024px wide, and in the action panel's footer below that.

The support contact email SHALL come from deployment configuration, never a hard-coded address. The footer SHALL show no support contact when none is configured. No retired brand name or domain ("VisitorPass", "Visimio") SHALL appear on the page.

#### Scenario: Product identity is shown
- **WHEN** a visitor loads the landing page in a viewport 1440px wide
- **THEN** the Visimio logo (alt text "Visimio") and "© {current year} Visimio. All rights reserved." are visible in the brand panel

#### Scenario: Product identity on a phone
- **WHEN** a visitor loads the landing page in a viewport 360px wide
- **THEN** the Visimio logo is visible in the top strip and the copyright line is shown at the bottom of the page

#### Scenario: Support and legal links are present
- **WHEN** a visitor loads the landing page
- **THEN** the action panel's footer displays a Privacy Policy link, a Terms of Service link, and, when a support email is configured, a "Support Contact: {address}" mailto link to that address

#### Scenario: No support email configured
- **WHEN** a visitor loads the landing page in a deployment with no support email configured
- **THEN** the footer shows the Privacy Policy and Terms of Service links and no support contact line, and no `visitorpass` address appears anywhere on the page

### Requirement: Landing page fits a desktop viewport without scrolling
The landing page SHALL use the split-screen layout shared with the sign-in pages:
- a brand panel on the left from 1024px wide;
- an action panel on the right;
- below 1024px wide, a top strip with the logo and a "Visitor Portal" tag, with the action panel below it.

The brand panel SHALL show:
- the lobby photo under a navy gradient;
- the headline "Welcome to the Visitor Portal";
- the tagline;
- three visitor highlights.

Brand panel layout:
- it SHALL fill the full viewport height;
- its photo SHALL cover the panel;
- the photo SHALL NOT be downloaded on viewports narrower than 1024px.

When the viewport is at least 1024px wide and at least 700px tall, all of the following SHALL be visible with no vertical page scroll:
- the brand panel;
- the action panel's heading;
- both cards, including their call-to-action labels;
- the footer links.

When the viewport is shorter or narrower:
- only the action panel SHALL scroll;
- the brand panel or top strip SHALL stay in place;
- no content SHALL be clipped or hidden.

#### Scenario: Full-HD desktop shows the whole landing page
- **WHEN** a visitor loads the landing page in a browser viewport 1920px wide and about 866px tall
- **THEN** the brand panel, the action panel heading, the "Request a Visit" and "Track Your Visit" cards, and the footer links are all visible, and the page has no vertical scrollbar

#### Scenario: Minimum supported desktop height
- **WHEN** a visitor loads the landing page in a viewport 1024px wide and 700px tall
- **THEN** both cards and the footer links are visible without vertical scrolling

#### Scenario: Tall viewport has no empty gap
- **WHEN** a visitor loads the landing page in a viewport 1920px wide and 1200px tall
- **THEN** the brand panel fills the full height, and the action panel's heading and cards stay vertically centred in their panel

#### Scenario: Short viewport scrolls instead of clipping
- **WHEN** a visitor loads the landing page in a viewport 1366px wide and 560px tall
- **THEN** the brand panel stays in place, the action panel scrolls, and every element (both cards and the footer links) can be reached and is fully visible once scrolled into view

#### Scenario: Phone layout unchanged
- **WHEN** a visitor loads the landing page in a viewport 360px wide
- **THEN** the top strip shows the logo and "Visitor Portal" tag, the cards are stacked in a single column, nothing overflows horizontally, and the action panel scrolls to reach the second card and the footer
