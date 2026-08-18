---
trigger: model_decision
description: Apply when building or modifying an endpoint that accepts a file upload — visitor photos, ID document scans, bulk-import CSVs, or any multipart/form-data route.
---

# File Upload Handling — VMSS_API

`security-architecture.md` §4 covers PII storage/encryption for documents/photos
once they're saved. This covers the upload path itself, before that point.

## 1. Size Limits

- Enforce a max upload size per endpoint (e.g. 5 MB for a photo, 10 MB for an ID
  scan — tune per artifact type) checked against `Content-Length` / streamed byte
  count before reading the full body into memory. Don't let an unbounded upload
  reach the point of buffering the whole file into a Python object first.

## 2. Content Validation, Not Just the Client's Say-So

- Validate actual file content — decode the image with Pillow, check real magic
  bytes (e.g. via `python-magic`) — rather than trusting the client-supplied
  `Content-Type` header or the filename extension. A renamed `.exe` with a `.jpg`
  extension and a spoofed `Content-Type: image/jpeg` header is the standard bypass
  for extension/header-only checks.
- Reject anything outside an explicit allow-list (`image/jpeg`, `image/png`,
  `application/pdf` for document scans) rather than a deny-list.

## 3. Storage

- Uploads go straight to the object-storage tier behind the storage interface
  (`database-architecture.md` §1) — never buffered to local disk outside of dev,
  never inlined as a DB column. Generate the storage key server-side
  (`vmss:{tenant_id}:...` convention); never trust a client-supplied path or
  filename as part of the storage key (path traversal risk).

## 4. Malware/Content Scanning

- Flagged as a required pre-production item for ID-document and photo uploads
  (e.g. ClamAV or a hosted scanning API in the upload pipeline) — treat this as an
  open item to confirm with the security-architecture owner before launch, not
  something to silently skip because "it's just an image."
