## Purpose

The admin-kiosks capability is the Admin's Kiosks register at `/admin/kiosks`, plus its Add/Edit Kiosk page: it lets an admin view, add, edit, hide/unhide, and delete the company-wide kiosks used for visitor check-in.

## ADDED Requirements

### Requirement: Kiosks section requires an authenticated session
The system SHALL check for a staff auth token before rendering the Kiosks list or the Add/Edit Kiosk page, and SHALL redirect to `/admin/login` instead of rendering when no token is present or when any kiosk request returns 401.

#### Scenario: No token on the list
- **WHEN** a browser without a staff auth token navigates to `/admin/kiosks`
- **THEN** the system redirects to `/admin/login` and does not render the page

#### Scenario: Token expires mid-session
- **WHEN** a kiosk request returns 401
- **THEN** the system sends the user to the admin login

### Requirement: Kiosks are company-wide
The system SHALL send kiosk requests without any branch scoping header and SHALL NOT offer a branch selector on the Kiosks screens.

#### Scenario: Kiosk request headers
- **WHEN** the system requests or mutates kiosks
- **THEN** the request carries the bearer token and no `X-Branch-ID` header

### Requirement: Kiosk list loads with pagination and defaults
The system SHALL, on entering the Kiosks page, fetch page 1 with a page size of 20, sorted by name ascending, excluding hidden kiosks, and render one row per kiosk showing its name, description, and Active status. The system SHALL provide previous/next paging driven by the returned pagination totals.

#### Scenario: Kiosks load successfully
- **WHEN** the Kiosks page loads and the fetch succeeds
- **THEN** the table shows one row per kiosk and paging controls reflecting the total

#### Scenario: Zero kiosks
- **WHEN** the list loads successfully with zero kiosks
- **THEN** the system shows the shared empty state instead of table rows

#### Scenario: Load failure
- **WHEN** the list fails to load
- **THEN** the system shows an error message, triggers an error notification, and allows retrying without a page reload

### Requirement: Kiosk list can be filtered by status
The system SHALL let the admin filter the list by All, Active, or Inactive. "All" SHALL omit the status parameter; the other options SHALL send `status=active` or `status=inactive`. Changing the filter SHALL reset to page 1.

#### Scenario: Filter to inactive
- **WHEN** the admin selects "Inactive"
- **THEN** the system requests `status=inactive` from page 1 and shows only inactive kiosks

#### Scenario: Clear filter
- **WHEN** the admin selects "All"
- **THEN** the request omits the status parameter

### Requirement: Kiosk list can be sorted
The system SHALL let the admin sort by name or created date, ascending or descending, sending only `name` or `created_at` as the sort field, and SHALL reset to page 1 when the sort changes.

#### Scenario: Sort by created date descending
- **WHEN** the admin picks created date, descending
- **THEN** the system requests `sortBy=created_at&sortOrder=desc`

### Requirement: Hidden kiosks are excluded by default and revealable
The system SHALL exclude hidden kiosks from the list by default and SHALL offer a "Show hidden" toggle that, when on, requests `includeHidden=true`. Rows for hidden kiosks SHALL display a "Hidden" badge.

#### Scenario: Show hidden on
- **WHEN** the admin turns on "Show hidden"
- **THEN** the system requests `includeHidden=true` and hidden kiosks appear with a "Hidden" badge

#### Scenario: Show hidden off
- **WHEN** "Show hidden" is off
- **THEN** hidden kiosks do not appear in the list

### Requirement: Write actions require manage permission
The system SHALL show Add, Edit, Hide/Unhide, Delete, and the Active toggle only to users with kiosk manage rights. Users with view-only rights SHALL see the list read-only. The Add/Edit routes SHALL NOT render the form for users without manage rights.

#### Scenario: Manager sees write actions
- **WHEN** a user with manage rights views the Kiosks list
- **THEN** the Add button and per-row Edit, Hide/Unhide, and Delete actions are shown

#### Scenario: Viewer sees no write actions
- **WHEN** a user with view-only rights views the Kiosks list
- **THEN** no Add button and no per-row write actions are shown

#### Scenario: Server denies with 403
- **WHEN** any kiosk request returns 403
- **THEN** the system shows a "you do not have permission" message and makes no local change

### Requirement: Adding a kiosk validates name and description
The system SHALL provide an Add Kiosk page with name, description, and an Active toggle (default on). The system SHALL require a name of 1–255 characters (after trimming) and SHALL limit description to 2000 characters, showing field errors and not submitting when invalid. A successful create SHALL return the admin to the list with a success notification.

#### Scenario: Name missing
- **WHEN** the admin submits with an empty name
- **THEN** the system shows "name is required" on the name field and sends no request

#### Scenario: Name too long
- **WHEN** the admin enters a name over 255 characters or a description over 2000 characters
- **THEN** the system shows a length error on that field and sends no request

#### Scenario: Successful create
- **WHEN** the admin submits a valid form
- **THEN** the system creates the kiosk, shows a success notification, and returns to the list

### Requirement: Editing a kiosk updates name, description, and active state
The system SHALL provide an Edit Kiosk page, pre-filled from the single-kiosk fetch (which works for hidden kiosks), that updates name, description, and isActive without changing hidden state. The Active state SHALL also be togglable from the list row, independent of Hide/Unhide.

#### Scenario: Edit prefilled
- **WHEN** the admin opens `/admin/kiosks/:id/edit` for an existing kiosk, including a hidden one
- **THEN** the form is pre-filled with the kiosk's current values

#### Scenario: Edit does not change visibility
- **WHEN** the admin saves an edit
- **THEN** the request contains no hidden-state field and the kiosk's hidden state is unchanged

#### Scenario: Toggle active from the list
- **WHEN** the admin flips the Active toggle on a row
- **THEN** only the active state changes; the kiosk's hidden state is unchanged

### Requirement: Hide and unhide are separate from active state
The system SHALL let a manager hide or unhide a kiosk through a dedicated action that changes only hidden state, and SHALL NOT change the kiosk's Active status. After hiding while "Show hidden" is off, the kiosk SHALL disappear from the list.

#### Scenario: Hide a kiosk
- **WHEN** the manager hides an active kiosk with "Show hidden" off
- **THEN** the kiosk leaves the list and remains active when shown again via "Show hidden"

#### Scenario: Unhide a kiosk
- **WHEN** the manager unhides a hidden kiosk
- **THEN** its "Hidden" badge is removed and it appears in the default list

### Requirement: Deleting a kiosk requires confirmation
The system SHALL show a confirm dialog naming the kiosk and warning that deletion cannot be undone before deleting. Cancelling SHALL make no request. A successful delete SHALL remove the row and show a success notification.

#### Scenario: Confirm delete
- **WHEN** the manager activates Delete and confirms
- **THEN** the kiosk is deleted, the list refreshes, and a success notification is shown

#### Scenario: Cancel delete
- **WHEN** the manager activates Delete and cancels
- **THEN** no request is sent and the kiosk remains

### Requirement: Kiosk API errors are mapped to user-facing behavior
The system SHALL show a 409 (duplicate name) as an inline error on the name field, SHALL treat a 404 as "kiosk no longer exists" by notifying the user and refreshing the list (or returning to the list from the form), and SHALL show 422 validation failures as an error message without losing entered values.

#### Scenario: Duplicate name
- **WHEN** create or edit returns 409
- **THEN** the name field shows that the name is already used and the entered values are kept

#### Scenario: Kiosk deleted elsewhere
- **WHEN** an edit, hide, or delete returns 404
- **THEN** the system notifies the user that the kiosk no longer exists and refreshes the list

#### Scenario: Validation failure
- **WHEN** a request returns 422
- **THEN** the system shows the validation message and keeps the form values

### Requirement: Admin sidebar exposes Kiosks
The system SHALL add a "Kiosks" item to the Admin sidebar, marked active on `/admin/kiosks` and its sub-routes.

#### Scenario: Navigate via sidebar
- **WHEN** the admin selects "Kiosks" in the sidebar
- **THEN** the system navigates to `/admin/kiosks` with the item shown active
