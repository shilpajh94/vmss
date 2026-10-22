import { useMemo } from 'react'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import type { OrganisationConfig } from '../../../../domain/entities/organisation-config-schema'
import { timezoneOptions } from '../../../utils/timezones'

interface GeneralInformationCardProps {
  form: OrganisationConfig
  nameError?: string
  onNameChange: (organisationName: string) => void
  onTimezoneChange: (defaultTimezone: string) => void
}

// The logo picker that used to sit here only previewed a file locally (the API
// has no logo upload), so it was removed; branding is gap register G13.
export function GeneralInformationCard({ form, nameError, onNameChange, onTimezoneChange }: GeneralInformationCardProps) {
  const timezones = useMemo(() => timezoneOptions(form.defaultTimezone), [form.defaultTimezone])

  return (
    <section className="flex flex-1 flex-col gap-5 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <h2 className="font-display text-lg font-bold text-text">General Information</h2>

      <TextField
        label="Organisation Name"
        required
        value={form.organisationName}
        onChange={onNameChange}
        error={nameError}
        maxLength={255}
      />

      <SelectField
        label="Default Timezone"
        value={form.defaultTimezone}
        onChange={onTimezoneChange}
        options={timezones}
        required
      />
    </section>
  )
}
