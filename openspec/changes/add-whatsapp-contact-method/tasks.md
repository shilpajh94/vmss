## 1. Domain & types

- [x] 1.1 Add `PreferredContactMethodSchema`, type, and label map in `src/domain/entities/preferred-contact-method.ts`
- [x] 1.2 Use it in `visitor-schema.ts`, `staff-visitor-schema.ts`, `staff-visitor-lookup-schema.ts`
- [x] 1.3 Replace `'email' | 'sms'` in `visitor-request/types.ts`, `staff-visitor-registration/types.ts`, and `ReviewConfirmStep.tsx`

## 2. Validation

- [x] 2.1 Add Indian mobile number helper under `src/presentation/utils/`
- [x] 2.2 `use-visitor-request-wizard.ts`: require phone for `whatsapp`; apply Indian-number check for whatsapp/sms
- [x] 2.3 `use-staff-visitor-registration-wizard.ts`: same rules

## 3. UI

- [x] 3.1 `VisitorFieldsForm.tsx`: add WhatsApp option; phone `required` for whatsapp; remove cast to `'email' | 'sms'`
- [x] 3.2 `PrimaryContactCard.tsx`: same for the walk-in form
- [x] 3.3 `ReviewConfirmStep.tsx`: use label map so WhatsApp displays correctly
- [x] 3.4 `visitor-request.tsx`: replace email/sms prefill guard with schema `safeParse`
- [x] 3.5 Confirm lookup prefill in staff wizard carries `whatsapp` through

## 4. Verify & release

- [x] 4.1 Run `tsc`/lint and build
- [x] 4.2 Manually check both forms: WhatsApp selected without phone, with non-Indian phone, with valid phone; email/sms unchanged
- [x] 4.3 Deploy only after the backend with WhatsApp support is live in the target environment
