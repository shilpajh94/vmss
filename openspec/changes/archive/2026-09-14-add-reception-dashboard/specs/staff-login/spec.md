## MODIFIED Requirements

### Requirement: Successful sign-in lands on a role-based dashboard
The system SHALL, once a login request succeeds and the auth token is stored, determine the signed-in user's roles and navigate to `/admin/dashboard` when the user has the Admin role, to `/reception/dashboard` when the user has the Reception role (and not the Admin role), or to `/staff/dashboard` otherwise.

#### Scenario: Admin reaches the Admin Dashboard
- **WHEN** a user with the Admin role signs in successfully
- **THEN** the system navigates to `/admin/dashboard`

#### Scenario: Reception user reaches the Reception Dashboard
- **WHEN** a user with the Reception role, but not the Admin role, signs in successfully
- **THEN** the system navigates to `/reception/dashboard`

#### Scenario: Other staff reach the staff dashboard
- **WHEN** a user with neither the Admin nor the Reception role signs in successfully
- **THEN** the system navigates to `/staff/dashboard`
