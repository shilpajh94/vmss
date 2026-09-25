import { CustomFieldsSection } from '../../../../components/dynamic-fields/CustomFieldsSection'
import { DynamicField, type DynamicFieldValue } from '../../../../components/dynamic-fields/DynamicField'
import { resolveGroupFlatValues } from '../../../../components/dynamic-fields/field-group-visibility'
import { FieldGroupsSection } from '../../../../components/dynamic-fields/FieldGroupsSection'
import type { GroupInstance } from '../../../../components/dynamic-fields/RepeatableFieldGroup'
import type { EffectiveFormFieldGroup, FormField } from '../../../../../domain/entities/form-builder-schema'
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
  /** Ungrouped, admin-authored fields on this step beyond the seeded
   * `items`/`item_description` fields (add-generic-custom-field-support) —
   * a field belonging to one of `groups` below is excluded here, rendered
   * through `FieldGroupsSection` instead. Shared bucket with Visit
   * Details/custom steps, see `VisitRequestFormState.customFieldValues`.
   */
  customFields: FormField[]
  customFieldValues: Record<string, DynamicFieldValue>
  onCustomFieldValuesChange: (value: Record<string, DynamicFieldValue>) => void
  /** Carried Items' own admin-defined field groups
   * (add-repeatable-field-groups / add-conditional-field-groups), e.g. a
   * repeatable "Items Carried" group — rendered via `FieldGroupsSection`,
   * same pattern as Visitor Info/Vehicle Info's own groups. */
  groups: EffectiveFormFieldGroup[]
  /** Every non-system Carried Items field, including grouped ones — used to
   * resolve `groups`' `fieldKeys` (`customFields` above excludes them). */
  groupFields: FormField[]
  groupValues: Record<string, GroupInstance[]>
  onGroupValuesChange: (groupValues: Record<string, GroupInstance[]>) => void
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
  customFields,
  customFieldValues,
  onCustomFieldValuesChange,
  groups,
  groupFields,
  groupValues,
  onGroupValuesChange,
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
        fields={customFields}
        value={customFieldValues}
        onChange={onCustomFieldValuesChange}
        uploadFile={uploadFile}
        getFilePreviewUrl={getFilePreviewUrl}
      />
      <FieldGroupsSection
        groups={groups}
        fields={groupFields}
        flatValues={resolveGroupFlatValues(groups, groupValues, customFieldValues)}
        groupValues={groupValues}
        onGroupValuesChange={onGroupValuesChange}
        uploadFile={uploadFile}
        getFilePreviewUrl={getFilePreviewUrl}
      />
      {fields.length === 0 && groups.length === 0 && <p className="text-body text-text-muted">No details are required for this step.</p>}
    </div>
  )
}
