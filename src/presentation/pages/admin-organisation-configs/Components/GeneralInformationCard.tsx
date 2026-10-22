import { useMemo } from 'react'
import { FileUploadField } from '../../../components/ui/FileUploadField'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import type { OrganisationConfig } from '../../../../domain/entities/organisation-config-schema'
import { timezoneOptions } from '../../../utils/timezones'

const LOGO_ALLOWED_TYPES = ['image/png', 'image/jpeg']

interface LogoPreview {
  url: string
  fileName: string
}

interface GeneralInformationCardProps {
  form: OrganisationConfig
  nameError?: string
  logoPreview: LogoPreview | undefined
  onNameChange: (organisationName: string) => void
  onTimezoneChange: (defaultTimezone: string) => void
  onPreviewLogo: (file: File) => Promise<string>
  onLogoPreviewChange: (fileRef: string | undefined, fileName: string | undefined) => void
}

export function GeneralInformationCard({
  form,
  nameError,
  logoPreview,
  onNameChange,
  onTimezoneChange,
  onPreviewLogo,
  onLogoPreviewChange,
}: GeneralInformationCardProps) {
  const timezones = useMemo(() => timezoneOptions(form.defaultTimezone), [form.defaultTimezone])

  return (
    <section className="flex flex-1 flex-col gap-5 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <h2 className="font-display text-lg font-bold text-text">General Information</h2>

      <TextField label="Organisation Name" required value={form.organisationName} onChange={onNameChange} error={nameError} />

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
        options={timezones}
      />
    </section>
  )
}
