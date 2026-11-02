## ADDED Requirements

### Requirement: Approval Email Asks the Visitor to Bring ID When the Flow Is On
When the badge print flow is enabled for the tenant, the visitor's approval **email** (HTML and plain-text parts) SHALL state that the visit is approved and that the visitor should bring their ID. SMS and WhatsApp messages SHALL NOT change. When the flow is off the email SHALL be byte-identical to the existing one.

#### Scenario: Flow on
- **WHEN** an invitation is approved for a tenant with the flow on
- **THEN** the email includes the bring-your-ID callout

#### Scenario: Flow off
- **WHEN** the flow is off
- **THEN** the email is unchanged
