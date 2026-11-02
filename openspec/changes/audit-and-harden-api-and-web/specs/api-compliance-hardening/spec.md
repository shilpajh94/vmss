## ADDED Requirements

### Requirement: Idempotency Keys Are Scoped to One Endpoint, Caller, and Request
A cached idempotent response SHALL be replayed only for a retry of the same
logical request: the same tenant, HTTP method and route, the same caller
(the authenticated user, the device, or for public OTP routes the
identifier being verified), and the same request body. Reusing a key with
a different endpoint, caller or body SHALL NOT return the cached response.
Instead it SHALL be rejected with 422 and a message saying the key was
already used for a different request. While the first request with a key
is still being processed, a concurrent request with the same key SHALL be
rejected with 409 rather than executed a second time.

#### Scenario: Same key on a different endpoint does not replay
- **WHEN** a caller checks in an invitation with `Idempotency-Key: K` and
  then sends `Idempotency-Key: K` to the check-out endpoint
- **THEN** the check-out request is rejected with 422, and the check-in
  response is not returned

#### Scenario: OTP verify key cannot replay another identifier's proof token
- **WHEN** an OTP verify request for identifier A succeeds with
  `Idempotency-Key: K`, and a second verify request for identifier B
  arrives with the same key
- **THEN** the second request does not receive A's proof token

#### Scenario: Concurrent duplicates execute once
- **WHEN** two identical check-in requests with the same key arrive while
  the first is still running
- **THEN** exactly one check-in is performed, and the other request
  receives 409

#### Scenario: Genuine retry still replays
- **WHEN** a request is retried with the same key, endpoint, caller and
  body inside the cache window
- **THEN** the original response is returned without re-executing the
  mutation, exactly as today

### Requirement: Multipart Uploads Are Bounded in Total Size and File Count
Every multipart endpoint SHALL reject a request whose total body exceeds the
configured maximum, or whose number of file parts exceeds the configured
maximum, with 413 in the standard error envelope. It SHALL do so before
buffering the whole body. Per-file size and content validation SHALL be
unchanged.

#### Scenario: Oversized multipart body
- **WHEN** a client sends `POST /invitations` with a body larger than the
  configured total maximum
- **THEN** the response is 413, and no invitation or stored file is created

#### Scenario: Too many file parts
- **WHEN** a client sends more file parts than the configured maximum
- **THEN** the response is 413

#### Scenario: Normal upload is unaffected
- **WHEN** a client submits an invitation within both limits
- **THEN** it is processed exactly as today
