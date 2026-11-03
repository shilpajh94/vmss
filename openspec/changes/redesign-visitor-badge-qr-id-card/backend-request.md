# Backend request: badge data as JSON

The frontend now renders the visitor badge (ID-card design with a QR code) and prints it from the browser. It needs the badge data instead of a PDF.

## Endpoints
- `POST /checkin/{visitId}/badge` (print)
- `GET /checkin/{visitId}/badge?reason=` (reprint)

## Response (`Content-Type: application/json`)
Either `{ "data": {...} }` or the object itself:

```json
{
  "token": "<signed badge token, same one the QR carries today>",
  "visitorName": "Joseph George",
  "purpose": "Meeting",
  "hostName": "Brown Walsh",
  "photoUrl": "<URL the browser can load in an <img>, or a data: URL>"
}
```

- `purpose`, `hostName`, `photoUrl` may be null.
- Same rules as today: 409s for unapproved / no photo / ID not verified / badge already active; reprint invalidates the previous token.
- If `photoUrl` needs auth, return a data URL or a short-lived signed URL.

## Compatibility
The frontend accepts both: JSON renders the new card, `application/pdf` keeps opening the old PDF. So the backend can ship this at any time.
