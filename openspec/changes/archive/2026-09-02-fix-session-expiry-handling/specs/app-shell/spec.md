## ADDED Requirements

### Requirement: An expired or invalid session is handled gracefully, not as a generic error
The system SHALL, when a request to an authenticated endpoint receives a 401 or 403 response, clear the stored session token instead of attempting to parse the response body as a successful result, and SHALL, from anywhere in the app, show the user a message indicating their session has expired and redirect them to the appropriate sign-in page (`/admin/login` or `/staff/login`), rather than surfacing a generic or technical error message.

#### Scenario: Authenticated request receives a 401 or 403
- **WHEN** any request to an endpoint configured with `hasToken: true` receives a 401 or 403 response
- **THEN** the system clears the stored session token and does not treat the response body as valid data

#### Scenario: User is redirected with a clear message
- **WHEN** the system detects a 401 or 403 on an authenticated request
- **THEN** the user sees a message indicating their session has expired and is redirected to the sign-in page appropriate to the area of the app they were in

#### Scenario: Redirect works regardless of which page triggered the expiry
- **WHEN** the 401 or 403 occurs on a request made from any authenticated admin or staff page, not only the page that first loaded the token
- **THEN** the same session-expired message and redirect occur without requiring that page's own code to detect it individually
