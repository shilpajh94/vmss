## ADDED Requirements

### Requirement: Deployed Environments Trust Their Ingress for the Client Address
Every deployed environment (DEV, STAGE, PROD) SHALL configure the trusted
proxy setting with the address range of the load balancer or ingress that
fronts the API. A per-IP rate limit SHALL therefore never be a single
bucket shared by every client that reaches the API through that ingress.
An environment that cannot yet set the range SHALL NOT enable the per-IP
limits on authenticated, high-volume read endpoints (signed file URLs,
email assets, the effective registration form).

#### Scenario: Many staff load photos at once in production
- **WHEN** 50 staff on different networks open boards in production
  within the same minute, each loading their own visitors' photos
  through signed file URLs
- **THEN** no request is rejected with 429, because each client is
  counted against its own address and not the ingress's

#### Scenario: A single client exceeds its own limit
- **WHEN** one client sends more requests than the per-IP limit allows
  within a minute
- **THEN** only that client receives 429 and the standard error envelope,
  and other clients behind the same ingress are unaffected
