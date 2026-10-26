## MODIFIED Requirements

### Requirement: The Public Portal Footer Is Compact
The footer shared by the public pages (visitor request, tracking, not-found and route error pages) SHALL take only the height its content needs. The visitor portal landing page uses the split-screen layout instead, and its action-panel footer follows the same limits.
- From 1024px wide upward, the logo, tagline and copyright line SHALL sit
  on one row, with the policy links and support contact on the same row,
  and the footer SHALL be no taller than 88px when its content fits on
  one row.
- Below 1024px the blocks SHALL stack, with no more than 16px of vertical
  padding above and below the footer content.
- The footer logo SHALL stay 28px tall. The tagline, the copyright line,
  and any configured Privacy Policy, Terms of Service and support contact
  links SHALL still be shown.
- Links SHALL keep the touch target sizes required by "Controls Are
  Touch-Operable".

#### Scenario: Error page footer on a full-HD desktop
- **WHEN** the "Something went wrong" page renders in a viewport 1920px
  wide and about 866px tall
- **THEN** the footer is no taller than 88px and shows the logo, tagline
  and copyright line on one row

#### Scenario: Landing page footer with all links configured
- **WHEN** the visitor portal landing page renders at 1440px wide with the
  privacy, terms and support settings all configured
- **THEN** the action panel's footer shows all three links on one row, no
  taller than 88px, and the brand panel carries the logo and copyright line

#### Scenario: Track page footer with all links configured
- **WHEN** the visitor track page renders at 1440px wide with the privacy,
  terms and support settings all configured
- **THEN** the shared footer shows the brand block and all three links on
  one row, no taller than 88px

#### Scenario: Footer on a phone
- **WHEN** any public page renders at 360px wide
- **THEN** the footer blocks are stacked, nothing overflows horizontally,
  and the footer's vertical padding is no more than 16px at the top and
  bottom
