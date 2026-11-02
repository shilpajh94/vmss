## ADDED Requirements

### Requirement: Placeholder Secrets Are Refused Outside Local and Testing
When the configured environment is anything other than `local` or
`testing`, and secret enforcement is turned on, the system SHALL refuse to
start if the token-signing secret is empty, is the shipped placeholder
value, or is shorter than 32 characters. With enforcement off (the
default), it SHALL start and emit a warning instead. Either message SHALL
name the offending setting but SHALL NOT print its value.

#### Scenario: Production with the placeholder secret
- **WHEN** the environment is `production`, secret enforcement is on, and
  the token-signing secret is the shipped placeholder
- **THEN** the application exits at startup with an error naming the
  setting

#### Scenario: Enforcement not yet turned on
- **WHEN** the environment is `production`, secret enforcement is off, and
  the secret is too short
- **THEN** the application starts and logs a warning naming the setting

#### Scenario: Local development keeps working
- **WHEN** the environment is `local` and the placeholder secret is in use
- **THEN** the application starts normally

### Requirement: The Container Image Defaults to a Non-Debug Environment
The deployable container image SHALL default the environment setting to
`production`, so a deployment that forgets to set it runs with debug mode
off. Local development (DDEV) SHALL keep setting its own environment
explicitly.

#### Scenario: Container started without an environment variable
- **WHEN** the API container starts with no environment setting supplied
- **THEN** it runs as `production`, with debug mode disabled
