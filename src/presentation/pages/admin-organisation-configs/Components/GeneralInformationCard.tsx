import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import type { OrganisationConfig } from '../../../../domain/entities/organisation-config-schema'

const TIMEZONE_OPTIONS = [
  { value: 'GMT+00:00', label: 'GMT+00:00 (London, Lisbon)' },
  { value: 'GMT-05:00', label: 'GMT-05:00 (New York, Toronto)' },
  { value: 'GMT-08:00', label: 'GMT-08:00 (Los Angeles, Vancouver)' },
  { value: 'GMT+01:00', label: 'GMT+01:00 (Paris, Berlin)' },
  { value: 'GMT+05:30', label: 'GMT+05:30 (Mumbai, Colombo)' },
  { value: 'GMT+08:00', label: 'GMT+08:00 (Singapore, Hong Kong)' },
]

interface GeneralInformationCardProps {
  form: OrganisationConfig
  onNameChange: (organisationName: string) => void
  onTimezoneChange: (defaultTimezone: string) => void
  onLogoUrlChange: (logoUrl: string | undefined) => void
}

export function GeneralInformationCard({
  form,
  onNameChange,
  onTimezoneChange,
  onLogoUrlChange,
}: GeneralInformationCardProps) {
  return (
    <section className="flex flex-1 flex-col gap-5 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <h2 className="font-display text-lg font-bold text-text">General Information</h2>

      <TextField label="Organisation Name" value={form.organisationName} onChange={onNameChange} />

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
        options={TIMEZONE_OPTIONS}
      />
    </section>
  )
}
