## Purpose

The app-shell capability is the bootstrapped application surface: the routed shell that renders on load, the dependency-injection contract pages use to reach use cases, and the base HTTP client contract every future feature builds on.

## ADDED Requirements

### Requirement: Application renders a routed shell on load
The system SHALL render a root layout at the application's base route when loaded in a browser, with no unhandled errors.

#### Scenario: App loads at root route
- **WHEN** a user navigates to the application's base URL
- **THEN** a placeholder home page renders inside the root layout

### Requirement: Dependencies are available to presentation only through a provider
The system SHALL expose application dependencies (use cases) to React components exclusively through a dependency-injection provider and its accompanying hook.

#### Scenario: Component reads dependencies via hook
- **WHEN** a page component calls the dependencies hook
- **THEN** it receives the dependencies object without importing infrastructure or composition-root code directly

#### Scenario: Hook used outside provider
- **WHEN** the dependencies hook is called from a component not wrapped by the provider
- **THEN** the system throws a descriptive error instead of returning undefined

### Requirement: HTTP client enforces token presence for authenticated endpoints
The system SHALL refuse to send a request to an endpoint marked as requiring a token when no token is present, without making a network call.

#### Scenario: Authenticated endpoint called without a stored token
- **WHEN** a request is made to an endpoint configured with `hasToken: true` and no token exists in session storage
- **THEN** the system throws an error before issuing the network request

#### Scenario: Authenticated endpoint called with a stored token
- **WHEN** a request is made to an endpoint configured with `hasToken: true` and a token exists in session storage
- **THEN** the system attaches the token as an `Authorization: Bearer` header on the outgoing request

### Requirement: HTTP client validates response shape
The system SHALL validate every successful HTTP response against a schema before returning data to the caller.

#### Scenario: Response matches expected shape
- **WHEN** a request succeeds and the response body matches the provided schema
- **THEN** the caller receives the parsed, validated data

#### Scenario: Response does not match expected shape
- **WHEN** a request succeeds but the response body does not match the provided schema
- **THEN** the system raises a validation error instead of returning unvalidated data

### Requirement: API base URL is configured from environment
The system SHALL derive the API base URL from the `VITE_API_BASE_URL` environment variable at startup, with no trailing slash.

#### Scenario: Base URL is read at composition time
- **WHEN** the application composition root resolves the HTTP client
- **THEN** it uses the value of `VITE_API_BASE_URL` with any trailing slash removed
