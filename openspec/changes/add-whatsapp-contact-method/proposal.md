## Why

The backend now delivers visitor notifications (registration pending, confirmed, denied, rescheduled, details changed) over WhatsApp as well as email and SMS via Fast2SMS, and accepts `preferredContactMethod: "whatsapp"`. The UI only offers Email and SMS and hard-codes `'email' | 'sms'` in several places, so visitors cannot choose WhatsApp and a returned `"whatsapp"` value would be dropped or mislabelled.

## What Changes

- Add a "WhatsApp" option to the Preferred Contact Method selector on the visitor pre-registration wizard and the staff walk-in registration form.
- Treat the phone field as required when WhatsApp is selected (same as SMS), with client-side validation matching the backend rule "phone is required when preferredContactMethod is 'whatsapp'".
- Widen the `preferredContactMethod` Zod schemas and form types to `email | sms | whatsapp`, so requests and responses (including the visitor-lookup and portal prefill) accept the new value.
- Display "WhatsApp" wherever the contact method is shown (review/confirm step) and keep it when pre-filling the wizard from a returning visitor's profile, replacing hard-coded email/sms checks with a shared label/guard helper.
- Validate Indian mobile number format client-side when WhatsApp (or SMS) is selected, since the API accepts other numbers but delivery fails.
- OTP channel: no UI change. `whatsapp` already exists in `OtpChannelSchema`; existing 503 "channel unavailable" handling is kept.
- Rollout constraint: the UI option must ship only after the backend is deployed (older backends reject `"whatsapp"` with a validation error).

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `visitor-request-wizard`: Preferred contact method gains WhatsApp; phone required for WhatsApp; Indian-number check; WhatsApp preserved in prefill and review.
- `staff-visitor-registration`: Preferred contact method for the walk-in primary contact gains WhatsApp with the same phone requirement.

## Impact

- Schemas: `src/domain/entities/visitor-schema.ts`, `staff-visitor-schema.ts`, `staff-visitor-lookup-schema.ts` (enum widening); `visitor-portal-schema.ts` already a string.
- Types/validation: `visitor-request/types.ts`, `staff-visitor-registration/types.ts`, both wizard hooks.
- UI: `VisitorFieldsForm.tsx`, `PrimaryContactCard.tsx`, `ReviewConfirmStep.tsx`, `visitor-request.tsx` (prefill guard).
- No endpoint, composition-root or dependency changes. Existing tenants' form-builder configs still list only email/sms; the contact-method selector is currently hard-coded in the UI so it is unaffected (see design).
