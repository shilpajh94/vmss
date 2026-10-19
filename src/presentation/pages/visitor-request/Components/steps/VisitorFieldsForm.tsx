import { CustomFieldsSection } from '../../../../components/dynamic-fields/CustomFieldsSection'
import type { PreferredContactMethod } from '../../../../../domain/entities/preferred-contact-method'
import { FileUploadField } from '../../../../components/ui/FileUploadField'
import { SegmentedToggle } from '../../../../components/ui/SegmentedToggle'
import { SelectField } from '../../../../components/ui/SelectField'
import { TextField } from '../../../../components/ui/TextField'
import type { FormField } from '../../../../../domain/entities/form-builder-schema'
import type { VisitorInfoFieldState } from '../../hooks/use-visitor-request-wizard'
import type { VisitorCategoriesFieldState, VisitorFormEntry } from '../../types'

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
  /** Locks the "Full Name" field read-only — set only for a returning
   * visitor's primary contact, since the invitation-creation API silently
   * discards any edit to an already-known contact's name. Never set for an
   * additional group visitor. */
  fullNameLocked?: boolean
  visitorCategoriesState: VisitorCategoriesFieldState
  onRetryVisitorCategories?: () => void
  /** Branch-configured (form-builder) active/required state for ID proof
   * and profile photo — see `use-visitor-request-wizard.ts`.
   */
  visitorInfoFields: VisitorInfoFieldState
  /** Admin-authored (non-system) Visitor Info fields
   * (add-generic-custom-field-support) — this visitor's own answers live
   * on `value.customFieldValues`, independent of every other visitor's. */
  customFields: FormField[]
}

export function VisitorFieldsForm({
  value,
  onChange,
  showContactMethod,
  showExtendedFields = true,
  uploadFile,
  getFilePreviewUrl,
  errors,
  fullNameLocked,
  visitorCategoriesState,
  onRetryVisitorCategories,
  visitorInfoFields,
  customFields,
}: VisitorFieldsFormProps) {
  // A category can only ever come from the real, API-loaded catalog — never
  // a hardcoded placeholder (fix-visitor-category-invalid-id-fallback), since
  // any fake id would fail the backend's UUID validation on submission.
  const visitorCategoryOptions = visitorCategoriesState.categories.map((category) => ({
    value: category.id,
    label: category.name,
  }))
  const isCategoryLoading = visitorCategoriesState.status === 'loading'
  const isCategoryUnavailable =
    visitorCategoriesState.status === 'error' ||
    (visitorCategoriesState.status === 'loaded' && visitorCategoriesState.categories.length === 0)

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <TextField
        label="Full Name"
        placeholder="Full name"
        value={value.fullName}
        onChange={(fullName) => onChange({ ...value, fullName })}
        error={errors?.fullName}
        required
        readOnly={fullNameLocked}
        helperText={fullNameLocked ? 'Name on file for this contact' : undefined}
      />
      <TextField
        label="Email Address"
        placeholder="Email address"
        type="email"
        value={value.email}
        onChange={(email) => onChange({ ...value, email })}
        error={errors?.email}
        required={showContactMethod ? (value.preferredContactMethod ?? 'email') === 'email' : undefined}
      />
      <TextField
        label="Phone Number"
        placeholder="Phone number"
        type="tel"
        value={value.phone}
        onChange={(phone) => onChange({ ...value, phone })}
        error={errors?.phone}
        required={showContactMethod ? (value.preferredContactMethod === 'sms' || value.preferredContactMethod === 'whatsapp') : undefined}
      />
      {showExtendedFields && (
        <div className="flex flex-col gap-1.5">
          <SelectField
            label="Visitor Category"
            placeholder={
              isCategoryLoading ? 'Loading categories…' : isCategoryUnavailable ? 'Unable to load categories' : 'Select category'
            }
            options={visitorCategoryOptions}
            value={value.visitorCategory}
            onChange={(visitorCategory) => onChange({ ...value, visitorCategory })}
            error={errors?.visitorCategory}
            required
            disabled={isCategoryLoading || isCategoryUnavailable}
          />
          {isCategoryUnavailable && (
            <div className="flex items-center gap-2">
              <p className="text-caption text-danger">Couldn't load visitor categories.</p>
              <button
                type="button"
                onClick={onRetryVisitorCategories}
                className="text-caption font-semibold text-secondary-accent underline"
              >
                Retry
              </button>
            </div>
          )}
        </div>
      )}
      {showContactMethod && (
        <div className="flex flex-col gap-1.5">
          <span className="text-body font-medium text-text">Preferred Contact Method</span>
          <SegmentedToggle
            options={[
              { value: 'email', label: 'Email' },
              { value: 'sms', label: 'SMS' },
              { value: 'whatsapp', label: 'WhatsApp' },
            ]}
            value={value.preferredContactMethod ?? 'email'}
            onChange={(preferredContactMethod) =>
              onChange({ ...value, preferredContactMethod: preferredContactMethod as PreferredContactMethod })
            }
            variant="divided"
          />
          {errors?.preferredContactMethod && <p className="text-caption text-danger">{errors.preferredContactMethod}</p>}
        </div>
      )}
      {visitorInfoFields.idProofActive && (
        <>
          <SelectField
            label="ID Proof Type"
            placeholder="Select ID type"
            options={visitorInfoFields.idProofOptions.map((option) => ({ value: option, label: option }))}
            value={value.idProofType}
            onChange={(idProofType) => onChange({ ...value, idProofType })}
            error={errors?.idProofType}
            required={visitorInfoFields.idProofRequired}
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
            required={visitorInfoFields.idProofRequired}
          />
        </>
      )}
      {showExtendedFields && visitorInfoFields.profilePhotoActive && (
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
          required={visitorInfoFields.profilePhotoRequired}
        />
      )}
      {customFields.length > 0 && (
        <div className="col-span-full">
          <CustomFieldsSection
            fields={customFields}
            value={value.customFieldValues}
            onChange={(customFieldValues) => onChange({ ...value, customFieldValues })}
            uploadFile={uploadFile}
            getFilePreviewUrl={getFilePreviewUrl}
          />
        </div>
      )}
    </div>
  )
}
