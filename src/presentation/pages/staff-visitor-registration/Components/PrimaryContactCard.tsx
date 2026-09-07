import { FileUploadField } from '../../../components/ui/FileUploadField'
import { SegmentedToggle } from '../../../components/ui/SegmentedToggle'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'
import type { StaffVisitorFormEntry } from '../types'
import { ID_PROOF_ALLOWED_TYPES, ID_PROOF_OPTIONS, PROFILE_IMAGE_ALLOWED_TYPES } from './constants'
import { InlineFileUpload } from './InlineFileUpload'

interface PrimaryContactCardProps {
  value: StaffVisitorFormEntry
  onChange: (value: StaffVisitorFormEntry) => void
  uploadFile: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
  errors: Record<string, string>
  visitorCategories?: VisitorCategory[]
}

export function PrimaryContactCard({ value, onChange, uploadFile, getFilePreviewUrl, errors, visitorCategories }: PrimaryContactCardProps) {
  const visitorCategoryOptions = (visitorCategories ?? []).map((category) => ({ value: category.id, label: category.name }))

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-6">
      <h3 className="font-display text-base font-semibold text-text">Primary Contact Details</h3>

      <div className="grid grid-cols-3 gap-4">
        <TextField
          label="Full Name"
          placeholder="Full name"
          value={value.fullName}
          onChange={(fullName) => onChange({ ...value, fullName })}
          error={errors.fullName}
          required
        />
        <div className="flex flex-col gap-1.5">
          <TextField
            label="Email Address"
            placeholder="Email address"
            type="email"
            value={value.email}
            onChange={(email) => onChange({ ...value, email })}
            error={errors.email}
            required={(value.preferredContactMethod ?? 'email') === 'email'}
          />
          <p className="text-caption text-text-muted">OTP will be sent to this email</p>
        </div>
        <TextField
          label="Phone Number"
          placeholder="Phone number"
          type="tel"
          value={value.phone}
          onChange={(phone) => onChange({ ...value, phone })}
          error={errors.phone}
          required={value.preferredContactMethod === 'sms'}
        />
        <SelectField
          label="Visitor Category"
          placeholder="Select category"
          options={visitorCategoryOptions}
          value={value.visitorCategory}
          onChange={(visitorCategory) => onChange({ ...value, visitorCategory })}
          error={errors.visitorCategory}
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-body font-medium text-text">Preferred Contact Method</span>
          <SegmentedToggle
            options={[
              { value: 'email', label: 'Email' },
              { value: 'sms', label: 'SMS' },
            ]}
            value={value.preferredContactMethod ?? 'email'}
            onChange={(preferredContactMethod) => onChange({ ...value, preferredContactMethod: preferredContactMethod as 'email' | 'sms' })}
            variant="divided"
          />
        </div>

        <div className="flex items-end gap-3">
          <div className="flex-1">
            <SelectField
              label="ID Proof Type"
              placeholder="Select ID type"
              options={ID_PROOF_OPTIONS}
              value={value.idProofType}
              onChange={(idProofType) => onChange({ ...value, idProofType })}
              error={errors.idProofType}
              required
            />
          </div>
          <InlineFileUpload
            label="Upload"
            allowedTypes={ID_PROOF_ALLOWED_TYPES}
            fileName={value.idProofFileName}
            previewUrl={getFilePreviewUrl?.(value.idProofFileRef)}
            onUpload={uploadFile}
            onFileRefChange={(idProofFileRef, idProofFileName) => onChange({ ...value, idProofFileRef, idProofFileName })}
            error={errors.idProofFileRef}
            required
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <FileUploadField
          label="Profile Image"
          helperText="PNG or JPG (max 5MB)"
          allowedTypes={PROFILE_IMAGE_ALLOWED_TYPES}
          fileName={value.profileImageFileName}
          previewUrl={getFilePreviewUrl?.(value.profileImageFileRef)}
          onUpload={uploadFile}
          onFileRefChange={(profileImageFileRef, profileImageFileName) => onChange({ ...value, profileImageFileRef, profileImageFileName })}
          error={errors.profileImageFileRef}
        />
      </div>
    </div>
  )
}
