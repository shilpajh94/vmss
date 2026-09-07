## Context

`primary_contact_photo_file` is currently an optional multipart part on
both `POST /invitations` (`invitations/router.py::create_invitation`) and
`POST /registrations/walk-in` (`registrations/router.py::
create_walk_in_registration`, which forwards straight into
`invitations/service.py::create_invitation` — see proposal.md's Impact).
The primary-contact ID-proof file (`primary_contact_id_proof_file`) is
already mandatory on both, using the exact pattern (`Annotated[UploadFile,
File(...)]`, no default) this change applies to the photo field too.

## Goals / Non-Goals

**Goals:**
- Make the primary contact's photo mandatory on both endpoints, with
  identical validation to the existing mandatory ID-proof file.
- Leave co-visitor photo capture, and every other part of the multipart
  contract, unchanged.

**Non-Goals:**
- No change to the QR check-in/check-out cycle — confirmed already
  correct (proposal.md). No spec or code change for it in this change.
- No retroactive backfill for invitations created before this change with
  no primary contact photo — `primary_contact_photo_storage_key` stays a
  nullable column; existing rows are simply grandfathered with `null`.
- No new malware/content-scanning requirement beyond what
  `file-upload-handling.md` §4 already flags as an open pre-production
  item — unaffected by this change.

## Decisions

### 1. Tighten `v1` in place, not a new `v2`
`api-conventions.md` §2 normally requires a breaking change (here:
tightening validation on an existing param) to ship as a new version
prefix, with the old one deprecated rather than mutated. This change
deliberately does the opposite — confirmed directly with the product
owner — because the photo requirement is a correctness/verification gap
serious enough to want enforced everywhere immediately, not opt-in via a
new endpoint existing clients can ignore. Consequence: the web portal,
Flutter app, and walk-in kiosk must all be updated to send a primary
contact photo before (or atomically with) this deploying, or every
creation request from an un-updated client starts failing with a
validation error.

### 2. Same required-file shape as the existing ID-proof file, not new validation logic
`primary_contact_photo_file` goes from
`Annotated[UploadFile | None, File(...)] = None` to
`Annotated[UploadFile, File(...)]` (no default) on both routers —
identical to `primary_contact_id_proof_file`'s existing declaration. In
`invitations/service.py::create_invitation`, `primary_contact_photo_content`
changes from `bytes | None` to `bytes`, and its validate/store branch
(currently `if primary_contact_photo_content is not None: ...`) becomes
unconditional, mirroring the ID-proof content's own unconditional
validate/store lines immediately above it. No new validation function —
`_validate_photo` is reused exactly as today, just always called instead
of conditionally.

### 3. `registrations/service.py` needs no change
It already forwards `primary_contact_photo_content` straight into
`invitations_service.create_invitation` without inspecting it — only its
own router's parameter declaration changes (Decision 2), matching the
invitations router's edit.

## Risks / Trade-offs

- [Existing API clients (web portal, Flutter app, walk-in kiosk) that
  don't yet send a primary contact photo start failing on their next call
  after this deploys] → Accepted per Decision 1; requires coordinated
  client rollout, not a phased server-side migration. Flag to the client
  teams before this deploys.
- [A tenant with existing invitations created before this change has some
  rows with `primaryContactPhotoUrl: null`] → Expected and harmless — the
  column was already nullable, and every response schema already treats
  it as `str | None`; no reader assumes non-null.

## Open Questions

None — both ambiguities (co-visitor scope, versioning approach) were
resolved with the user before this design was written; see proposal.md.
