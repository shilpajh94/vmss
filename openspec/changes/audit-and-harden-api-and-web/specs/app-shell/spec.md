## MODIFIED Requirements

### Requirement: An expired or invalid session is handled gracefully, not as a generic error
The system SHALL, when a request to an authenticated endpoint receives a 401 response, clear the stored session token instead of attempting to parse the response body as a successful result, and SHALL, from anywhere in the app, show the user a message indicating their session has expired and redirect them to the appropriate sign-in page (`/admin/login` or `/staff/login`), rather than surfacing a generic or technical error message. A 403 response SHALL NOT end the session: it means the signed-in user is not permitted to perform that action, and the system SHALL show a "not permitted" message while keeping the user signed in on the current page.

#### Scenario: Authenticated request receives a 401 or 403
- **WHEN** any request to an endpoint configured with `hasToken: true` receives a 401 response
- **THEN** the system clears the stored session token and does not treat the response body as valid data
- **AND** a 403 response is instead handled as described in "A 403 keeps the session"

#### Scenario: User is redirected with a clear message
- **WHEN** the system detects a 401 on an authenticated request
- **THEN** the user sees a message indicating their session has expired and is redirected to the sign-in page appropriate to the area of the app they were in

#### Scenario: Redirect works regardless of which page triggered the expiry
- **WHEN** the 401 occurs on a request made from any authenticated admin or staff page, not only the page that first loaded the token
- **THEN** the same session-expired message and redirect occur without requiring that page's own code to detect it individually

#### Scenario: A 403 keeps the session
- **WHEN** an authenticated request receives a 403 response
- **THEN** the session token is kept, the user stays on the current page, and a "not permitted" message is shown

## ADDED Requirements

### Requirement: Admin and Staff Areas and Their Actions Are Gated by the Caller's Permissions
The admin area (`/admin/*` except its sign-in page) SHALL be available only
to a signed-in user whose permissions (from the current-user profile's
per-branch `permissionCodes`) include at least one admin-management
permission. Anyone else SHALL be redirected to their own landing page and
shown a "not permitted" message. The session check SHALL run once at the
layout, not separately in each page. Navigation entries and action buttons
whose permission the caller lacks SHALL be hidden. A tenant-defined role
SHALL get exactly the UI its permissions allow, regardless of its name.

#### Scenario: Reception user opens an admin URL
- **WHEN** a signed-in Reception user without admin-management permissions
  opens `/admin/branches`
- **THEN** they are redirected to the reception dashboard with a "not
  permitted" message, and no admin page content renders

#### Scenario: Security user sees no Register Visitor action
- **WHEN** a signed-in user whose permissions lack `invitations:create`
  views their dashboard or sidebar
- **THEN** no "Register Visitor" entry is shown

#### Scenario: Custom role with check-out permission
- **WHEN** a user whose only role is tenant-defined but grants
  `invitations:checkout` opens the invitations board
- **THEN** the check-out action is available on checked-in cards

### Requirement: An Unknown Route Shows a Not-Found Page
Navigating to a path that matches no route SHALL render a not-found page
with a link back to the appropriate home page (the landing page, or the
signed-in user's dashboard), never a blank screen.

#### Scenario: Mistyped URL
- **WHEN** a user opens `/admin/brnches`
- **THEN** a not-found page with a link home is shown

### Requirement: Signing Out Ends the Server Session
Signing out SHALL call the API's logout endpoint before clearing the local
session. A failure of that call SHALL NOT stop the local sign-out.

#### Scenario: Normal sign-out
- **WHEN** a signed-in user activates Sign out
- **THEN** the logout endpoint is called, the local session is cleared,
  and the user lands on the sign-in page

#### Scenario: Logout call fails
- **WHEN** the logout request fails or times out
- **THEN** the local session is still cleared and the user still lands on
  the sign-in page

### Requirement: Master-Data Requests Carry the Session Token When One Exists
A request to a master-data listing endpoint (branches, buildings, floors,
departments, employees directory, visitor categories) SHALL include the
session token whenever the user is signed in. The API then resolves the
user's own tenant instead of the deployment default. Signed-out public
pages SHALL keep calling these endpoints without a token.

#### Scenario: Signed-in admin lists branches
- **WHEN** a signed-in admin opens the Branches page
- **THEN** the branch listing request carries the bearer token

#### Scenario: Public wizard lists departments
- **WHEN** a signed-out visitor loads the request wizard
- **THEN** the department listing request is sent without a token and
  succeeds

### Requirement: Unsaved Form Input Is Protected From Accidental Loss
When a create/edit form, either registration wizard, or the form-builder
field panel holds input that has not been saved, leaving it (in-app
navigation, the browser back button, closing the tab, or switching to
another field in the form builder) SHALL first ask the user to confirm
discarding the changes. A form with no unsaved changes SHALL be left
without a prompt. The wizard's Cancel action SHALL also confirm when input
exists.

#### Scenario: Navigating away from a half-filled wizard
- **WHEN** a staff user has typed into the Register Visitor wizard and
  clicks a sidebar link
- **THEN** a confirmation is shown, and the input is kept if they choose
  to stay

#### Scenario: Pristine form
- **WHEN** an admin opens an edit form and leaves without changing
  anything
- **THEN** no confirmation is shown

### Requirement: Option Pickers List Every Active Option
A dropdown or picker sourced from a list endpoint SHALL include every
active option, fetching further pages when there are more than one page
holds. It SHALL exclude inactive or soft-deleted options, so a user cannot
pick a value the API will reject. A stored value that refers to an inactive
option SHALL still display its name on edit.

#### Scenario: More than 100 employees
- **WHEN** a tenant has 140 active employees and an admin opens a host
  picker
- **THEN** all 140 are selectable

#### Scenario: Inactive visitor category
- **WHEN** a visitor category is inactive
- **THEN** it does not appear in the registration wizards' category
  picker
