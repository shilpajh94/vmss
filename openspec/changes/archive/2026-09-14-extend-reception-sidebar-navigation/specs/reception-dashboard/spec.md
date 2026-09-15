## MODIFIED Requirements

### Requirement: Page renders the Reception sidebar and top bar
The system SHALL render, for an authenticated Reception session, a sidebar with three navigation items — "Dashboard", "Visits", and "My actions" — and a top bar showing the signed-in user's name and role. On the Reception Dashboard page, "Dashboard" SHALL be marked active.

#### Scenario: Reception user views the Dashboard page
- **WHEN** an authenticated Reception user's Dashboard page finishes loading
- **THEN** the sidebar (with "Dashboard" marked active, alongside "Visits" and "My actions") and the top bar are visible

### Requirement: The Reception sidebar follows the user to the Visits and Register Visitor pages
The system SHALL, when a Reception user activates "Visits" or "My actions" in the Reception sidebar, navigate to the existing Visits board (`/staff/dashboard`) or Register Visitor wizard (`/staff/visitors/new`) respectively, and SHALL render the same Reception sidebar (not the plain staff sidebar) on those pages for a Reception-role session, with the matching item marked active.

#### Scenario: Reception user opens Visits
- **WHEN** a Reception user activates "Visits" in the Reception sidebar
- **THEN** the system navigates to `/staff/dashboard` and renders the Reception sidebar there, with "Visits" marked active

#### Scenario: Reception user opens My actions
- **WHEN** a Reception user activates "My actions" in the Reception sidebar
- **THEN** the system navigates to `/staff/visitors/new` and renders the Reception sidebar there, with "My actions" marked active
