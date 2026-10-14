## Context

`preferredContactMethod` is typed `'email' | 'sms'` in four Zod schemas (`visitor-schema`, `staff-visitor-schema`, `staff-visitor-lookup-schema`; `visitor-portal-schema` is already a loose string), two form-type files, two wizard validation hooks, two selector components, the review step's label function, and the prefill guard in `visitor-request.tsx`. The selector options are hard-coded in the UI, not read from the form-builder config. `OtpChannelSchema` already includes `whatsapp`. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Offer and submit WhatsApp on both forms, with phone required.
- Remove hard-coded email/sms assumptions so `whatsapp` round-trips through lookup, prefill, review.
- Client-side Indian mobile check for WhatsApp/SMS.

**Non-Goals:**
- Adding WhatsApp as an OTP channel in the UI (existing 503 handling stays; `resolveOtpChannel` unchanged).
- Rendering contact-method options from the form-builder config.
- Changes to endpoints, composition root, or other screens that do not show the field.

## Decisions

- **Single shared definition.** Add `src/domain/entities/preferred-contact-method.ts` exporting `PreferredContactMethodSchema = z.enum(["email","sms","whatsapp"])`, its inferred type, and a label map. Schemas and form types import it, so the enum lives in one place (matches the rule: one source of truth via `z.infer`). Alternative, editing each literal union, repeats the drift that caused this problem.
- **Tolerant parsing of responses.** The lookup schema's enum is widened; unknown values in prefill fall back to `undefined` via a `safeParse` guard instead of the `=== 'email' || === 'sms'` check, so a future value cannot crash the screen.
- **Indian-number validation** is a small pure helper in `presentation/utils` (regex for `+91`/`91`/`0` prefix + 10 digits starting 6–9, or bare 10 digits), applied only when method is whatsapp or sms. Applying it to SMS is a deliberate tightening: the backend note says non-Indian numbers fail to send for SMS too. Open to limiting it to WhatsApp if SMS must stay unchanged ("Nothing existing changes").
- **Rollout gating.** Because older backends reject `"whatsapp"`, ship the UI only after the backend is deployed to each environment. No feature flag is added; deployment ordering is the control.

## Risks / Trade-offs

- Shipping before the backend → submissions with WhatsApp fail validation. Mitigation: release ordering, noted in tasks.
- Stricter SMS phone validation may block numbers that previously submitted (and silently failed to deliver). Mitigation: error message is explicit; easy to scope to WhatsApp only.
- Existing tenants' form configs list only email/sms; harmless now since options are hard-coded, but becomes a gap if the selector later moves to config-driven options.
