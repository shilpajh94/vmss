## Purpose

Defines what must be true before a release that spans the API, the web
portal and the mobile app is merged and deployed, so a live server is never
left with a client that depends on an API it does not yet run.

## ADDED Requirements

### Requirement: The API Is Deployed Before the Clients That Depend on It
A release whose web or mobile changes read a field, header or behaviour
introduced by the same release SHALL deploy the API to an environment
before those clients. The release checklist SHALL name each such
dependency.

#### Scenario: Board approval actions in this release
- **WHEN** the web portal from this release, whose board cards read
  `currentApprovalStep` and `preferredVisitDate`/`preferredVisitTime` from
  the invitation list, is deployed to an environment
- **THEN** that environment already runs the API that returns those
  fields, so reception can still approve and delegate from the board

### Requirement: Tenant Migrations Run Before Traffic Uses the New Release
A release that adds tenant migrations SHALL apply them to every tenant
schema, inside a declared low-traffic window when a migration builds
indexes without `CONCURRENTLY`. The release SHALL remain correct if
traffic arrives before the migrations finish.

#### Scenario: Index migration on a busy tenant
- **WHEN** the operator runs the tenant upgrade for this release
- **THEN** it is run in the declared window, every tenant reports the new
  head revision afterwards, and requests served in between still succeed
  without the new indexes

### Requirement: Client-Visible Behaviour Changes Are Handed to the Mobile Team
Before a release reaches production, every API change a mobile client can
observe SHALL be listed in a mobile migration guide. Each entry SHALL give
the endpoint, the old and new behaviour, what the app must do, and whether
the app must ship it before this release, before strict public-endpoint
mode, or only as a recommendation.

#### Scenario: A behaviour change ships without the guide
- **WHEN** a release would make an existing app request return a
  different status code (for example, a group registration with no
  visitors now returns 422)
- **THEN** the release does not proceed to production until that change
  appears in the guide and the app team has acknowledged it

### Requirement: Strict Public-Endpoint Mode Waits for the Mobile Release
`PUBLIC_ENDPOINT_HARDENING` SHALL stay off in an environment until an app
release that sends every credential strict mode requires is live for that
environment's users. The app team SHALL confirm this before the flag is
turned on.

#### Scenario: Flag turned on before the app is ready
- **WHEN** an operator proposes enabling strict mode in production, but
  the store version of the app still calls `GET /invitations/track?email=`
  without a proof token
- **THEN** the flag stays off and the change is rescheduled after the app
  update reaches its users
