## ADDED Requirements

### Requirement: Top bar lists all of the signed-in user's roles
The system SHALL show, beneath the signed-in user's name in the top bar (admin, staff, and reception shells), every distinct role name assigned to that user, separated by commas, in the order the roles were granted. A role granted at more than one branch SHALL appear once. When the user has no role grants, the system SHALL show "Staff". When the list is too long for the available width, the system SHALL truncate it with an ellipsis on a single line and SHALL expose the full list through the element's title, so the top bar never grows taller.

#### Scenario: Single role
- **WHEN** a user with only the Reception role is signed in
- **THEN** the top bar shows "reception" under the user's name

#### Scenario: Multiple roles
- **WHEN** a user assigned the Reception and Host roles is signed in
- **THEN** the top bar shows both role names, e.g. "reception, host", under the user's name

#### Scenario: Same role at several branches
- **WHEN** a user has the Host role at two different branches
- **THEN** "host" appears once in the top bar

#### Scenario: No roles granted
- **WHEN** the signed-in user has no role grants
- **THEN** the top bar shows "Staff"

#### Scenario: Long role list
- **WHEN** the combined role names exceed the width available in the user block
- **THEN** the text is truncated with an ellipsis on one line and the full list is available as the element's title
