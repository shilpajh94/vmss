## MODIFIED Requirements

### Requirement: The primary contact's visitor category is submitted as the invitation's category
The system SHALL submit the primary contact's selected visitor category as the invitation-level visitor category, identified by that category's id, since the backend associates one visitor category with an invitation as a whole rather than per visitor. The submitted id SHALL always originate from the visitor-category catalog loaded from the API. The system SHALL NOT offer, or allow selection of, any placeholder visitor-category option that is not backed by a real id from that catalog.

#### Scenario: Submission includes the invitation's visitor category
- **WHEN** the visitor confirms submission
- **THEN** the submitted request includes the primary contact's selected visitor category's id as the invitation's visitor category

#### Scenario: A placeholder category can never be submitted
- **WHEN** the visitor-category catalog has not loaded, or has loaded with zero categories
- **THEN** the Visitor Category field offers no selectable options that are not backed by a real catalog id, so no invitation can be created referencing a non-existent category

## ADDED Requirements

### Requirement: Visitor Category field reflects the catalog's loading and failure states
The system SHALL show a loading indication for the Visitor Category field while the visitor-category catalog is being fetched. If the fetch fails or returns zero categories, the system SHALL show a distinguishable "unavailable" state with a way to retry, and SHALL NOT allow the Visitor Info step to be completed until a real category has been selected.

#### Scenario: Catalog is loading
- **WHEN** the visitor-category catalog fetch has not yet completed
- **THEN** the Visitor Category field shows a loading state rather than an empty or fake-populated dropdown

#### Scenario: Catalog fetch fails
- **WHEN** the visitor-category catalog fetch fails or returns zero categories
- **THEN** the Visitor Category field shows an error state with a way to retry the fetch, and the visitor cannot proceed past the Visitor Info step until a real category is available and selected

#### Scenario: Catalog loads successfully
- **WHEN** the visitor-category catalog fetch succeeds with at least one category
- **THEN** the Visitor Category field offers exactly those categories, each identified by its real id
