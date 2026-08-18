import { FileUploadField } from '../../../components/ui/FileUploadField'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import type { OrganisationConfig } from '../../../../domain/entities/organisation-config-schema'

const LOGO_ALLOWED_TYPES = ['image/png', 'image/jpeg']

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
  onUploadLogo: (file: File) => Promise<string>
  onLogoChange: (logoUrl: string | undefined) => void
}

export function GeneralInformationCard({ form, onNameChange, onTimezoneChange, onUploadLogo, onLogoChange }: GeneralInformationCardProps) {
  return (
    <section className="flex flex-1 flex-col gap-5 rounded-2xl border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-bold text-text">General Information</h2>

      <TextField label="Organisation Name" value={form.organisationName} onChange={onNameChange} />

      <FileUploadField
        label="Organisation Logo"
        helperText="PNG, JPG up to 5MB (Recommended 512x512)"
        allowedTypes={LOGO_ALLOWED_TYPES}
        previewUrl={form.logoUrl}
        onUpload={onUploadLogo}
        onFileRefChange={(logoUrl) => onLogoChange(logoUrl)}
      />

      <SelectField
        label="Default Timezone"
        value={form.defaultTimezone}
        onChange={onTimezoneChange}
        options={TIMEZONE_OPTIONS}
      />
    </section>
  )
}
