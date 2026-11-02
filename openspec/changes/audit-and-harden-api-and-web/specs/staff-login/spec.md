## MODIFIED Requirements

### Requirement: Successful sign-in lands on a role-based dashboard
The system SHALL, once a login request succeeds and the auth token is stored, return the user to the page they originally requested when sign-in was triggered by opening a protected page (including a deep link from a push notification or email, with its query string), provided that page is within the area the user is permitted to use. Otherwise, the system SHALL determine the signed-in user's roles and navigate to `/admin/dashboard` when the user has the Admin role, to `/reception/dashboard` when the user has the Reception role (and not the Admin role), or to `/staff/dashboard` otherwise. A return path SHALL only ever be a path within this app; any other value SHALL be ignored.

#### Scenario: Admin reaches the Admin Dashboard
- **WHEN** a user with the Admin role signs in successfully with no requested page pending
- **THEN** the system navigates to `/admin/dashboard`

#### Scenario: Reception user reaches the Reception Dashboard
- **WHEN** a user with the Reception role, but not the Admin role, signs in successfully with no requested page pending
- **THEN** the system navigates to `/reception/dashboard`

#### Scenario: Other staff reach the staff dashboard
- **WHEN** a user with neither the Admin nor the Reception role signs in successfully with no requested page pending
- **THEN** the system navigates to `/staff/dashboard`

#### Scenario: Deep link survives sign-in
- **WHEN** a signed-out staff user opens `/staff/invitations?invitationId=X` from a notification, is sent to sign in, and signs in successfully
- **THEN** the system navigates to `/staff/invitations?invitationId=X`

#### Scenario: External return path is ignored
- **WHEN** the sign-in page is opened with a return path pointing outside the app
- **THEN** a successful sign-in navigates to the role-based dashboard instead

## ADDED Requirements

### Requirement: The Password Is Submitted Exactly as Typed
The sign-in form SHALL send the password exactly as entered, with no
trimming or normalisation. The email MAY be trimmed.

#### Scenario: Password with a trailing space
- **WHEN** a user whose password ends in a space types it correctly and
  signs in
- **THEN** the password is sent with the trailing space and sign-in
  succeeds

### Requirement: Sign-In Failure Messages Distinguish Their Cause
A failed sign-in SHALL show:
- "Invalid email or password" only for rejected credentials;
- a "too many attempts, try again shortly" message for a rate-limit
  response;
- a "can't reach the server" message for a network failure or server
  error.

#### Scenario: Rate-limited sign-in
- **WHEN** a sign-in request is rejected with 429
- **THEN** the message says there have been too many attempts, not that
  the credentials are invalid

#### Scenario: Server unreachable
- **WHEN** the sign-in request fails with a network error or a 5xx
- **THEN** the message says the server can't be reached
