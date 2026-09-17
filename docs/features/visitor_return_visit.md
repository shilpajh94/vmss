# Visitor Return Visit (Returning-Visitor Self-Service Lookup)

Lets a visitor who has already verified an email or phone number via
`identity-verification`'s OTP flow retrieve their own prior visit history
and a prefill payload for a new registration — turning that flow's
`identity_verified` proof token (previously issued but not consumed by any
caller) into something useful, without creating a user account, JWT/RBAC
session, or any authenticated identity for the visitor. See
`openspec/changes/visitor-return-visit-login/` for the proposal/design this
feature was built from.

`visitor_return_visit` owns no table of its own — it reads existing
`Invitation` rows (the same table both staff pre-registration and visitor
walk-in registration write to) by contact match, and is entirely additive:
`POST /registrations/walk-in` and `POST /invitations` are unmodified.

## Endpoints

| Method | Path | Auth | Rate limit | Description |
|---|---|---|---|---|
| GET | `/api/v1/visitor-portal/me` | `identity_verified` proof token (bearer) | 20/minute per IP | Returns the verified identifier's own visit history (tracking ID, status, visit date, purpose — paginated) and, when at least one prior visit exists, a prefill payload (full name, email, phone, preferred contact method, ID proof type, ID proof URL, photo URL) drawn from the most recent one. A first-time identifier gets an empty history and a `null` prefill — a `200`, not an error. |

## Authentication: the verified-contact proof token, not a session

This endpoint accepts only the short-lived (15-minute) `identity_verified`
proof token minted by `POST /identity-verification/otp/verify`
(`core/security.py::create_identity_verified_token`) — never a staff
access/refresh token or any other token type. `visitor_return_visit/deps.py`'s
`verified_contact` dependency decodes the bearer token and rejects anything
whose `type` claim isn't `identity_verified`, since a plain `decode_token`
call alone doesn't distinguish token types.

The identifier looked up is **always** the one embedded in the token's own
claims — never a client-supplied value in the request body or query
string — so a caller can only ever retrieve data tied to an identifier they
just proved control of over OTP.

No `User` row, access/refresh token, or RBAC permission is ever created or
required by this flow; the visitor remains unauthenticated in `auth`'s
sense throughout.

## Tenant resolution

Like `identity-verification` and `registrations`, this public endpoint has
no tenant signal of its own (no bearer-token `tenant_id` claim is read, no
device credential) and resolves `settings.default_tenant_slug`
(`core/tenancy.py::resolve_default_tenant`) the same way those features do.
An unconfigured or inactive default tenant is a server-side
misconfiguration, logged at `ERROR` (event
`visitor_return_visit_default_tenant_unconfigured`) distinguishing "no such
tenant" from "tenant inactive", and reported to the caller as `404`.

## Prefill field naming

`ReturningVisitorPrefill`'s `id_proof_url`/`photo_url` fields follow the
same naming already used for a resolved document/photo URL everywhere else
in this codebase (e.g. `InvitationVisitorDetailOut.id_proof_url`,
`primary_contact_photo_url`) — deliberately *not* `form_builder`'s own
field keys (`id_proof_upload`/`profile_photo`). The client rendering this
payload has its own fixed mapping from these fields onto the walk-in
registration form; it does not look the prefill up generically by the
form's field configuration. (An earlier revision of this endpoint used the
`form_builder` key names instead and broke that client's existing
`photoUrl` contract at runtime — a `invalid_type`/`undefined` validation
error on `data.prefill.photoUrl` — confirming the client depends on this
exact name.)

## ID-proof document and photo access

Unlike a staff-facing view of someone else's visitor record — where access
to a raw identity-document image is its own permission (`documents:view`,
`security-architecture.md` §4) — `id_proof_url` and `photo_url` here are
the *same* visitor's own previously-submitted document and photo, returned
to them under the OTP-proven `identity_verified` proof token. This endpoint
has no authenticated staff caller and never will; the proof token itself
(proof of control over the identifier those documents were filed under) is
the access check, not `documents:view`. Both fields are `null`, never
omitted, when nothing was captured on the most recent prior visit.

## Relationship to walk-in registration

This capability is read-only: it does not create or modify a visit record,
and `POST /registrations/walk-in` is not changed to require or even accept
a proof token. A client that has fetched this endpoint's prefill data
simply pre-populates the existing walk-in registration form with it and
submits through that endpoint exactly as a first-time visitor would.
Whether walk-in registration should eventually *require* a proof token for
a returning visitor specifically is an open product question (see
`security-architecture.md` §2's "fake-entry prevention"), not something this
change decides.
