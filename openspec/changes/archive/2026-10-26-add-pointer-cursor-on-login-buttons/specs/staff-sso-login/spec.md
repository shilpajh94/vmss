## ADDED Requirements

### Requirement: Staff SSO sign-in action shows a pointer cursor
On the `/staff/login` screen, the "Sign in with SSO" button SHALL show the pointer (hand) cursor while the mouse is over it and it is enabled. While the button is disabled (redirecting to the identity provider or completing sign-in), it SHALL show the not-allowed cursor instead.

#### Scenario: Hovering the SSO button
- **WHEN** a user moves the mouse over the enabled "Sign in with SSO" button on `/staff/login`
- **THEN** the mouse cursor is the pointer (hand) cursor

#### Scenario: Hovering the SSO button while redirecting
- **WHEN** an SSO redirect or sign-in completion is in progress and the user moves the mouse over the disabled "Sign in with SSO" button
- **THEN** the mouse cursor is the not-allowed cursor, not the pointer cursor
