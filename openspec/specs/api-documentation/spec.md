# api-documentation Specification

## Purpose

Defines how the API's OpenAPI schema and Swagger/ReDoc UI are exposed, secured, and kept in sync with every endpoint the service actually serves.

## Requirements

### Requirement: OpenAPI documentation availability by environment
The system SHALL serve the Swagger UI (`/docs`), ReDoc UI (`/redoc`), and raw OpenAPI schema (`/openapi.json`) in the `local`, `dev`, and `staging` environments, and SHALL NOT serve them (returning 404) when the environment is `production`.

#### Scenario: Docs reachable in a non-production environment
- **WHEN** the API is running with environment `local`, `dev`, or `staging` and a client requests `/docs`
- **THEN** the response is `200` and renders the Swagger UI

#### Scenario: Docs disabled in production
- **WHEN** the API is running with environment `production` and a client requests `/docs`, `/redoc`, or `/openapi.json`
- **THEN** the response is `404`

### Requirement: Every registered endpoint is discoverable in the OpenAPI schema
Every route belonging to a router registered in `api_router` SHALL appear in the generated OpenAPI schema, grouped under its feature's tag.

#### Scenario: A feature's routes all appear in the schema
- **WHEN** the OpenAPI schema is generated for the running application
- **THEN** every path and method exposed by every router included in `api_router` is present in the schema's `paths`, tagged with that feature's tag

#### Scenario: A router left unregistered fails a test, not silently
- **WHEN** a feature package under `src/vmss_api/<feature>/router.py` defines a router that is not included in `api_router`
- **THEN** the automated router-registration check fails, rather than the endpoints simply being absent from the docs with nothing reporting it

### Requirement: Protected endpoints declare a bearer security requirement
Every endpoint that depends on `get_current_user` or `require_permission` SHALL be marked in the OpenAPI schema with a bearer-token security requirement, and the Swagger UI SHALL offer an "Authorize" flow that accepts a raw access token.

#### Scenario: Protected endpoint shows a lock and accepts a pasted token
- **WHEN** a client opens Swagger UI, uses "Authorize" to supply a valid access token obtained from `POST /auth/login`, and then uses "Try it out" on an endpoint guarded by `get_current_user` or `require_permission`
- **THEN** the request is sent with an `Authorization: Bearer <token>` header and receives the same response the endpoint would give any authenticated caller with that token

#### Scenario: Unauthenticated request against a protected endpoint is rejected the same way with or without docs
- **WHEN** a client calls a protected endpoint's "Try it out" without first authorizing
- **THEN** the response is `401`, identical to calling the endpoint directly without a token

### Requirement: Schema field names match the camelCase wire format
For every request/response schema derived from `CamelModel`, the OpenAPI schema SHALL render field names using the camelCase alias that the actual JSON wire format uses, not the underlying snake_case Python attribute name.

#### Scenario: A response schema shows camelCase fields
- **WHEN** the OpenAPI schema is generated for an endpoint whose response model extends `CamelModel` and has a field such as `organization_id`
- **THEN** the corresponding property in the schema is named `organizationId`, not `organization_id`

#### Scenario: A request body schema shows camelCase fields
- **WHEN** the OpenAPI schema is generated for an endpoint whose request body model extends `CamelModel`
- **THEN** every property in the request body schema uses its camelCase alias, matching what a client must actually send

### Requirement: OpenAPI metadata identifies the API and each feature
The generated OpenAPI schema SHALL include an application title, version, and description sourced from application settings, and SHALL include a description for each feature tag used by a registered router.

#### Scenario: Schema exposes application metadata
- **WHEN** the OpenAPI schema is generated
- **THEN** its `info` object contains a non-empty `title`, `version`, and `description`

#### Scenario: Each feature tag has a description
- **WHEN** the OpenAPI schema is generated
- **THEN** every tag referenced by a registered route appears in the schema's top-level `tags` list with a non-empty `description`
