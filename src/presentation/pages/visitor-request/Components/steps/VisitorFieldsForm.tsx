import { FileUploadField } from '../../../../components/ui/FileUploadField'
import { SegmentedToggle } from '../../../../components/ui/SegmentedToggle'
import { SelectField } from '../../../../components/ui/SelectField'
import { TextField } from '../../../../components/ui/TextField'
import type { VisitorCategory } from '../../../../../domain/entities/visitor-category-schema'
import type { VisitorFormEntry } from '../../types'

// Fallback when the visitor-categories master data can't be loaded (e.g. no
// staff session token available for an anonymous public visitor).
const VISITOR_CATEGORY_OPTIONS = [
  { value: 'general-visitor', label: 'General Visitor' },
  { value: 'contractor', label: 'Contractor' },
  { value: 'vendor', label: 'Vendor' },
  { value: 'interview-candidate', label: 'Interview Candidate' },
  { value: 'delivery', label: 'Delivery' },
  { value: 'vip', label: 'VIP' },
  { value: 'other', label: 'Other' },
]

// Values must match the backend's `idProofType` enum for
// POST /registrations/walk-in exactly (validated server-side against these 4 strings).
const ID_PROOF_OPTIONS = [
  { value: 'Aadhaar Card', label: 'Aadhaar Card' },
  { value: 'Passport', label: 'Passport' },
  { value: 'Driving License', label: 'Driving License' },
  { value: 'Other', label: 'Other' },
]

const ID_PROOF_ALLOWED_TYPES = ['image/png', 'image/jpeg', 'application/pdf']
const PROFILE_IMAGE_ALLOWED_TYPES = ['image/png', 'image/jpeg']

interface VisitorFieldsFormProps {
  value: VisitorFormEntry
  onChange: (value: VisitorFormEntry) => void
  showContactMethod: boolean
  // Visitor Category and Profile Image are primary-contact-only in practice —
  // group visitor drafts only collect the core identity fields.
  showExtendedFields?: boolean
  uploadFile: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
  errors?: Record<string, string>
  visitorCategories?: VisitorCategory[]
}

export function VisitorFieldsForm({
  value,
  onChange,
  showContactMethod,
  showExtendedFields = true,
  uploadFile,
  getFilePreviewUrl,
  errors,
  visitorCategories,
}: VisitorFieldsFormProps) {
  const visitorCategoryOptions = visitorCategories?.length
    ? visitorCategories.map((category) => ({ value: category.id, label: category.name }))
    : VISITOR_CATEGORY_OPTIONS

  return (
    <div className="grid grid-cols-2 gap-4">
      <TextField
        label="Full Name"
        placeholder="Full name"
        value={value.fullName}
        onChange={(fullName) => onChange({ ...value, fullName })}
        error={errors?.fullName}
        required
      />
      <TextField
        label="Email Address"
        placeholder="Email address"
        type="email"
        value={value.email}
        onChange={(email) => onChange({ ...value, email })}
        error={errors?.email}
        required
      />
      <TextField
        label="Phone Number"
        placeholder="Phone number"
        type="tel"
        value={value.phone}
        onChange={(phone) => onChange({ ...value, phone })}
        error={errors?.phone}
        required
      />
      {showExtendedFields && (
        <SelectField
          label="Visitor Category"
          placeholder="Select category"
          options={visitorCategoryOptions}
          value={value.visitorCategory}
          onChange={(visitorCategory) => onChange({ ...value, visitorCategory })}
          error={errors?.visitorCategory}
          required
        />
      )}
      {showContactMethod && (
        <div className="flex flex-col gap-1.5">
          <span className="text-body font-medium text-text">Preferred Contact Method</span>
          <SegmentedToggle
            options={[
              { value: 'email', label: 'Email' },
              { value: 'sms', label: 'SMS' },
            ]}
            value={value.preferredContactMethod ?? 'email'}
            onChange={(preferredContactMethod) =>
              onChange({ ...value, preferredContactMethod: preferredContactMethod as 'email' | 'sms' })
            }
            variant="divided"
          />
        </div>
      )}
      <SelectField
        label="ID Proof Type"
        placeholder="Select ID type"
        options={ID_PROOF_OPTIONS}
        value={value.idProofType}
        onChange={(idProofType) => onChange({ ...value, idProofType })}
        error={errors?.idProofType}
        required
      />
      <FileUploadField
        label="Upload ID"
        helperText="PNG, JPG or PDF (max 5MB)"
        allowedTypes={ID_PROOF_ALLOWED_TYPES}
        fileName={value.idProofFileName}
        previewUrl={getFilePreviewUrl?.(value.idProofFileRef)}
        onUpload={uploadFile}
        onFileRefChange={(idProofFileRef, idProofFileName) => onChange({ ...value, idProofFileRef, idProofFileName })}
        error={errors?.idProofFileRef}
        required
      />
      {showExtendedFields && (
        <FileUploadField
          label="Profile Image"
          helperText="PNG or JPG (max 5MB)"
          allowedTypes={PROFILE_IMAGE_ALLOWED_TYPES}
          fileName={value.profileImageFileName}
          previewUrl={getFilePreviewUrl?.(value.profileImageFileRef)}
          onUpload={uploadFile}
          onFileRefChange={(profileImageFileRef, profileImageFileName) =>
            onChange({ ...value, profileImageFileRef, profileImageFileName })
          }
          error={errors?.profileImageFileRef}
        />
      )}
    </div>
  )
}
