## MODIFIED Requirements

### Requirement: The Public Portal Footer Is Compact
The footer of the split-screen layout, at the bottom of the content panel on every public page, SHALL take only the height its content needs:
- From 1024px wide upward, the configured policy links and support contact
  SHALL sit on one row, and the footer SHALL be no taller than 88px when
  its content fits on one row. The logo and copyright line are in the
  brand panel at these widths.
- Below 1024px the copyright line and links SHALL stack, with no more than
  16px of vertical padding above and below the footer content.
- Any configured Privacy Policy, Terms of Service and support contact
  links SHALL be shown.
- Links SHALL keep the touch target sizes required by "Controls Are
  Touch-Operable".

#### Scenario: Error page footer on a full-HD desktop
- **WHEN** the "Something went wrong" page renders in a viewport 1920px
  wide and about 866px tall
- **THEN** the content panel's footer is no taller than 88px, and the
  brand panel shows the logo and copyright line

#### Scenario: Landing page footer with all links configured
- **WHEN** the visitor portal landing page renders at 1440px wide with the
  privacy, terms and support settings all configured
- **THEN** the content panel's footer shows all three links on one row, no
  taller than 88px, and the brand panel carries the logo and copyright line

#### Scenario: Track page footer with all links configured
- **WHEN** the visitor track page renders at 1440px wide with the privacy,
  terms and support settings all configured
- **THEN** the content panel's footer shows all three links on one row, no
  taller than 88px

#### Scenario: Footer on a phone
- **WHEN** any public page renders at 360px wide
- **THEN** the footer's copyright line and links are stacked, nothing
  overflows horizontally, and the footer's vertical padding is no more
  than 16px at the top and bottom
