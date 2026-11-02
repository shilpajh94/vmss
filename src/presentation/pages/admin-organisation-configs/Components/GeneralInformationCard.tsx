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
  onLogoUrlChange: (logoUrl: string | undefined) => void
}

export function GeneralInformationCard({ form, nameError, onNameChange, onTimezoneChange, onLogoUrlChange }: GeneralInformationCardProps) {
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

      <TextField
        label="Organisation Logo URL"
        type="url"
        value={form.logoUrl ?? ''}
        onChange={(logoUrl) => onLogoUrlChange(logoUrl.trim() || undefined)}
        placeholder="https://example.com/logo.svg"
        helperText="Public link to the logo image; this is what gets saved."
      />

      {form.logoUrl && (
        <img src={form.logoUrl} alt="Organisation logo preview" className="h-16 w-auto max-w-full self-start object-contain" />
      )}

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
