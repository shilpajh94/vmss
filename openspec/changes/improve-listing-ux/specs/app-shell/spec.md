## ADDED Requirements

### Requirement: A page's own heading and action row stays fixed while its data region scrolls
The system SHALL, for any page that renders a section heading (e.g. "Branches Register") together with that page's own Filters and primary action ("Add"/"Register"/etc.) controls above a table, board, or list, keep that heading-and-action row fixed in place within the page's content area and confine vertical scrolling caused by that page's data (table rows, board columns, list items) to the region beneath it — the same way the outer sidebar and top bar already stay fixed while the overall content area scrolls. This applies one level deeper than the existing sidebar/top-bar behavior: within a single page's own content, not just at the shell level.

#### Scenario: Long data list scrolls without moving the page heading
- **WHEN** a page's table, board, or list has enough rows/items to exceed the visible content height
- **THEN** the user can scroll to see the rest of the data while that page's heading, Filters control, and primary action button remain visible and stationary

#### Scenario: Short data list does not introduce an extra scrollbar
- **WHEN** a page's table, board, or list fits within the space available beneath its heading row
- **THEN** no scrollbar appears in the data region

#### Scenario: An open filter panel is part of the fixed region, not the scrolling region
- **WHEN** an admin activates "Filters" and the filter panel expands beneath the heading row
- **THEN** the filter panel remains fixed alongside the heading row, and only the table/board/list beneath the (possibly expanded) fixed region scrolls
