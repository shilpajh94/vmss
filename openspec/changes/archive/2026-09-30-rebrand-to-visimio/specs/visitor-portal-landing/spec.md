## MODIFIED Requirements

### Requirement: Landing page identifies the product and provides support/legal links
The system SHALL display the product name and a way to reach support or legal information on the landing page.

#### Scenario: Product identity is shown
- **WHEN** a visitor loads the landing page
- **THEN** the Visimio logo (alt text "Visimio") is visible in both the header and footer, and the footer carries "© {current year} Visimio. All rights reserved."

#### Scenario: Support and legal links are present
- **WHEN** a visitor loads the landing page
- **THEN** the footer displays a Privacy Policy link, a Terms of Service link, and a support contact email address
