## ADDED Requirements

### Requirement: Workflow list can be filtered by visitor category and status
The system SHALL show a functional "Filters" control on the Workflows list offering Visitor Category and Status fields (each defaulting to "All"), and SHALL, as soon as a filter changes, send the selected filters as query parameters on a fresh request to the underlying approval-workflow-rule list endpoint and re-render the visible groups from the returned result, without a separate confirm step. The system SHALL let an admin clear all active filters back to "All" in one action.

#### Scenario: Filters activated
- **WHEN** an admin activates "Filters" on the Workflows list
- **THEN** the system shows the Visitor Category and Status filter fields

#### Scenario: Filter selected narrows the list
- **WHEN** an admin selects a Visitor Category and/or Status value
- **THEN** the system requests the approval-workflow-rule list with those values as query parameters and only the matching groups remain visible

#### Scenario: Filters cleared
- **WHEN** an admin activates "Clear filters"
- **THEN** the system re-requests the rule list with no filter parameters and every configured workflow's group is shown again

#### Scenario: No filter matches shows a distinct empty state
- **WHEN** a filter is active and no workflow group matches it
- **THEN** the system shows a "no workflows match these filters" message, distinct from the message shown when zero workflows are configured at all

### Requirement: The workflow list's fetch is bounded but not paginated
The system SHALL fetch the underlying approval-workflow-rule list as a single bounded request (a `pageSize` large enough to cover realistic per-tenant rule volume — every visitor category's every approval level) rather than exposing page-forward/page-back controls. A workflow group's approval levels must all be present to render correctly and stay in step order; a page-by-page fetch could split one visitor category's levels across two pages, showing an incomplete or misordered workflow until an admin paged further — the same reasoning that exempts the Invitations Kanban board from pagination.

#### Scenario: Workflows page load requests a bounded page size
- **WHEN** the Workflows page loads (with or without filters active)
- **THEN** the request to the approval-workflow-rule list endpoint specifies a `pageSize` covering the configured bound, and no page-forward/page-back control is shown on this page

#### Scenario: A visitor category's levels are never split across pages
- **WHEN** a visitor category has multiple approval levels configured
- **THEN** all of that category's levels appear together in its group, in `stepOrder` order, regardless of how many other categories or levels exist
