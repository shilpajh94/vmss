## ADDED Requirements

### Requirement: Admin sign-in actions show a pointer cursor
On the `/admin/login` screen, the "Sign In" button and the "Sign in with SSO" button SHALL show the pointer (hand) cursor while the mouse is over them and they are enabled. While either button is disabled (a sign-in is in progress), it SHALL show the not-allowed cursor instead.

#### Scenario: Hovering the Sign In button
- **WHEN** a user moves the mouse over the enabled "Sign In" button on `/admin/login`
- **THEN** the mouse cursor is the pointer (hand) cursor

#### Scenario: Hovering the SSO button
- **WHEN** a user moves the mouse over the enabled "Sign in with SSO" button on `/admin/login`
- **THEN** the mouse cursor is the pointer (hand) cursor

#### Scenario: Hovering a button while sign-in is in progress
- **WHEN** a password sign-in is in progress and the user moves the mouse over the disabled "Sign In" or "Sign in with SSO" button
- **THEN** the mouse cursor is the not-allowed cursor, not the pointer cursor
