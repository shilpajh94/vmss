## MODIFIED Requirements

### Requirement: Landing page identifies the product and provides support/legal links
The system SHALL display the product name and a way to reach support or legal information on the landing page. The support contact email SHALL come from deployment configuration, never a hard-coded address, and the footer SHALL show no support contact when none is configured. No retired brand name or domain ("VisitorPass", "Visimio") SHALL appear in the footer.

#### Scenario: Product identity is shown
- **WHEN** a visitor loads the landing page
- **THEN** the Guestify logo (alt text "Guestify") is visible in both the header and footer, and the footer carries "© {current year} Guestify. All rights reserved."

#### Scenario: Support and legal links are present
- **WHEN** a visitor loads the landing page
- **THEN** the footer displays a Privacy Policy link, a Terms of Service link, and, when a support email is configured, a "Support Contact: {address}" mailto link to that address

#### Scenario: No support email configured
- **WHEN** a visitor loads the landing page in a deployment with no support email configured
- **THEN** the footer shows the Privacy Policy and Terms of Service links and no support contact line, and no `visitorpass` address appears anywhere on the page

