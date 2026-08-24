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

interface LogoPreview {
  url: string
  fileName: string
}

interface GeneralInformationCardProps {
  form: OrganisationConfig
  logoPreview: LogoPreview | undefined
  onNameChange: (organisationName: string) => void
  onTimezoneChange: (defaultTimezone: string) => void
  onPreviewLogo: (file: File) => Promise<string>
  onLogoPreviewChange: (fileRef: string | undefined, fileName: string | undefined) => void
}

export function GeneralInformationCard({
  form,
  logoPreview,
  onNameChange,
  onTimezoneChange,
  onPreviewLogo,
  onLogoPreviewChange,
}: GeneralInformationCardProps) {
  return (
    <section className="flex flex-1 flex-col gap-5 rounded-2xl border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-bold text-text">General Information</h2>

      <TextField label="Organisation Name" value={form.organisationName} onChange={onNameChange} />

      <FileUploadField
        label="Organisation Logo"
        helperText="PNG, JPG up to 5MB (Recommended 512x512) — preview only; logo upload isn't saved until the backend adds file storage support"
        allowedTypes={LOGO_ALLOWED_TYPES}
        fileName={logoPreview?.fileName}
        previewUrl={logoPreview?.url ?? form.logoUrl}
        onUpload={onPreviewLogo}
        onFileRefChange={onLogoPreviewChange}
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
