## ADDED Requirements

### Requirement: The Preferred Contact Method field offers WhatsApp for every tenant
The system-seeded Preferred Contact Method field SHALL include `whatsapp` among its options for every tenant, regardless of when the tenant was provisioned, in both its live draft configuration and in every published form configuration version for any scope. Existing options SHALL be kept and keep their order, with `whatsapp` added after them. A tenant that already lists `whatsapp` SHALL be left unchanged.

#### Scenario: A tenant provisioned before WhatsApp support is brought up to date
- **WHEN** a tenant whose Preferred Contact Method field lists only `email` and `sms` has pending schema upgrades applied
- **THEN** its draft field options become `email`, `sms`, `whatsapp`

#### Scenario: A published form configuration is also updated
- **WHEN** a scope of that tenant has been published and its snapshot lists only `email` and `sms`
- **THEN** the effective form served for that scope offers `whatsapp` without the tenant having to publish again

#### Scenario: Re-running the upgrade changes nothing
- **WHEN** the upgrade is applied again to a tenant that already lists `whatsapp`
- **THEN** no field or snapshot is modified and `whatsapp` is not duplicated

#### Scenario: Other fields are untouched
- **WHEN** the upgrade runs
- **THEN** no field other than Preferred Contact Method has its options, order or locked state changed
