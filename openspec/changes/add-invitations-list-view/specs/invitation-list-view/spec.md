## ADDED Requirements

### Requirement: Invitations pages offer a Board and a List view
The admin and staff Invitations pages SHALL show a view switch with "Board" and "List". The Board view SHALL be the default.

#### Scenario: First visit
- **WHEN** a user opens an Invitations page with no remembered choice
- **THEN** the Kanban board is shown and "Board" is the active option

#### Scenario: Switching to list
- **WHEN** the user selects "List"
- **THEN** the invitations appear as a list and the board is not rendered

#### Scenario: Choice is remembered
- **WHEN** the user selects "List" and later reopens the same portal's Invitations page
- **THEN** the List view is shown, and the admin and staff pages remember their choice separately

### Requirement: The list shows one row per invitation
In List view each loaded invitation SHALL be one row showing the visitor's avatar and name, tracking ID, a status chip, purpose of visit, point of contact, preferred visit date and time, and registration type. Rows SHALL be ordered by visit date and time, newest first.

#### Scenario: Row content
- **WHEN** the list renders an approved group invitation
- **THEN** its row shows the visitor, tracking ID, "Approved" status, purpose, date/time and a group indicator

#### Scenario: Missing optional values
- **WHEN** an invitation has no purpose or visit time
- **THEN** that cell shows "—" instead of being blank or failing

### Requirement: List shares the board's search and filters
The search box, purpose, registration type, status and source filters SHALL apply to the list exactly as they apply to the board, and switching views SHALL NOT clear them.

#### Scenario: Filter then switch
- **WHEN** a user filters by status "approved" on the board and switches to List
- **THEN** the list shows only approved invitations

#### Scenario: No matches
- **WHEN** no invitation matches the filters
- **THEN** the list shows an empty state, not a blank table

### Requirement: Row actions match the board and respect permissions
Each row SHALL offer the actions its status allows on the board (view info, approve, deny, reschedule, edit, delegate, check out, revert approval), only to users who hold the matching permission, and SHALL reuse the same confirmation dialogs.

#### Scenario: Permitted action
- **WHEN** a user with approve permission opens a submitted invitation's row actions and chooses Approve
- **THEN** the same approve flow as the board opens

#### Scenario: Not permitted
- **WHEN** a user lacks deny permission
- **THEN** no Deny action appears on any row

#### Scenario: Open details
- **WHEN** the user clicks a row's name or View action
- **THEN** the Visitor Info dialog for that invitation opens

### Requirement: The list loads more and handles load states
The list SHALL show a skeleton on first load and the page error state on failure. When statuses have more invitations on the server than are loaded, the list SHALL offer "Load more" and append further invitations without losing scroll position or filters.

#### Scenario: More available
- **WHEN** the server total for a status exceeds the loaded count
- **THEN** "Load more" is shown and appends the next page when used

### Requirement: The list is readable on small screens
Below the `lg` breakpoint the list SHALL render each invitation as a stacked card with the same information and actions, with no horizontal page scroll.

#### Scenario: Phone width
- **WHEN** the viewport is phone width and List is selected
- **THEN** invitations appear as cards that fit the width
