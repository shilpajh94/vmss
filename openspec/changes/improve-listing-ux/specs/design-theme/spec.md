## ADDED Requirements

### Requirement: Spacing tokens define the application's padding and gap scale
The system SHALL expose a defined spacing token scale (covering, at minimum, the page-level content padding, the gap between a page's heading row and its data region, and the internal padding of card/panel-style components such as a filter panel) that every page layout and shared component draws from, rather than each page repeating its own hand-picked pixel/rem values.

#### Scenario: Page content padding uses a spacing token
- **WHEN** a page's main content region is rendered
- **THEN** its outer padding resolves to a named spacing token rather than an unnamed utility value chosen independently per page

#### Scenario: A new page follows the same scale without copying markup
- **WHEN** a new admin list page is built using the shared page-content layout (see the `app-shell` capability's fixed-heading/scrollable-body requirement)
- **THEN** its padding and gaps match every existing list page's spacing by referencing the same tokens, not by copying another page's pixel values
