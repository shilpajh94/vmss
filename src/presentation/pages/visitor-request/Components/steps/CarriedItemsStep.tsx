import { CustomFieldsSection } from '../../../../components/dynamic-fields/CustomFieldsSection'
import { DynamicField, type DynamicFieldValue } from '../../../../components/dynamic-fields/DynamicField'
import type { FormField } from '../../../../../domain/entities/form-builder-schema'
import type { CarriedItemsFormState } from '../../types'

interface CarriedItemsStepProps {
  /** Active Carried Items fields from the resolved branch's published Form
   * Builder configuration. May be genuinely empty once loaded (an admin
   * configured zero fields for this step) — that's rendered as-is, not
   * masked by a hardcoded default list; see `isLoading` for the separate
   * "config hasn't resolved yet" state.
   */
  fields: FormField[]
  isLoading: boolean
  value: CarriedItemsFormState
  onChange: (value: CarriedItemsFormState) => void
  /** Answers for any admin-authored field on this step beyond the seeded
   * `items`/`item_description` fields (add-generic-custom-field-support) —
   * shared with Visit Details/custom steps, see `VisitRequestFormState.
   * customFieldValues`.
   */
  customFieldValues: Record<string, DynamicFieldValue>
  onCustomFieldValuesChange: (value: Record<string, DynamicFieldValue>) => void
  /** Required for an active `file_upload` custom field to render a working
   * upload control instead of falling back to "not supported". */
  uploadFile?: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
}

export function CarriedItemsStep({
  fields,
  isLoading,
  value,
  onChange,
  customFieldValues,
  onCustomFieldValuesChange,
  uploadFile,
  getFilePreviewUrl,
}: CarriedItemsStepProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <h3 className="text-h3 text-text">Carried Items</h3>
          <p className="text-body text-text-muted">Please declare any items you will be carrying into the premises for security clearance.</p>
        </div>
        <p className="text-body text-text-muted">Loading…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-h3 text-text">Carried Items</h3>
        <p className="text-body text-text-muted">Please declare any items you will be carrying into the premises for security clearance.</p>
      </div>
      {fields.map((field) => {
        if (field.key === 'items') {
          return (
            <DynamicField
              key={field.id}
              field={field}
              value={value.categories}
              onChange={(fieldValue) => onChange({ ...value, categories: Array.isArray(fieldValue) ? fieldValue : [] })}
            />
          )
        }
        if (field.key === 'item_description') {
          return (
            <DynamicField
              key={field.id}
              field={field}
              value={value.description}
              onChange={(fieldValue) => onChange({ ...value, description: typeof fieldValue === 'string' ? fieldValue : '' })}
            />
          )
        }
        return null
      })}
      <CustomFieldsSection
        fields={fields.filter((field) => !field.isSystem)}
        value={customFieldValues}
        onChange={onCustomFieldValuesChange}
        uploadFile={uploadFile}
        getFilePreviewUrl={getFilePreviewUrl}
      />
      {fields.length === 0 && <p className="text-body text-text-muted">No details are required for this step.</p>}
    </div>
  )
}
