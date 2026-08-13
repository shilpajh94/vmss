## Purpose

The visitor-portal-landing capability is the entry screen of the visitor-facing portal: it introduces the product and routes the visitor to either request a new visit or track an existing one.

## ADDED Requirements

### Requirement: Landing page presents both visitor entry points
The system SHALL render, at the portal's landing screen, one call-to-action to request a visit and one call-to-action to track an existing visit request, each visually distinct and independently actionable.

#### Scenario: Both entry points are visible
- **WHEN** a visitor loads the landing page
- **THEN** a "Request a Visit" action and a "Track Your Visit" action are both rendered and visible without further interaction

#### Scenario: Request entry point navigates to the request flow
- **WHEN** a visitor activates the "Request Visit" action
- **THEN** the system navigates to the visit-request route

#### Scenario: Track entry point navigates to the tracking flow
- **WHEN** a visitor activates the "Track Request" action
- **THEN** the system navigates to the visit-tracking route

### Requirement: Landing page identifies the product and provides support/legal links
The system SHALL display the product name and a way to reach support or legal information on the landing page.

#### Scenario: Product identity is shown
- **WHEN** a visitor loads the landing page
- **THEN** the product name "VisitorPass" is visible in both the header and footer

#### Scenario: Support and legal links are present
- **WHEN** a visitor loads the landing page
- **THEN** the footer displays a Privacy Policy link, a Terms of Service link, and a support contact email address
