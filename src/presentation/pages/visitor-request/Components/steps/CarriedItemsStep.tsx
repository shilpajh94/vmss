import { DynamicField } from '../../../../components/dynamic-fields/DynamicField'
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
}

export function CarriedItemsStep({ fields, isLoading, value, onChange }: CarriedItemsStepProps) {
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
      {fields.map((field) =>
        field.key === 'items' ? (
          <DynamicField
            key={field.id}
            field={field}
            value={value.categories}
            onChange={(fieldValue) => onChange({ ...value, categories: Array.isArray(fieldValue) ? fieldValue : [] })}
          />
        ) : (
          <DynamicField
            key={field.id}
            field={field}
            value={value.description}
            onChange={(fieldValue) => onChange({ ...value, description: typeof fieldValue === 'string' ? fieldValue : '' })}
          />
        ),
      )}
      {fields.length === 0 && <p className="text-body text-text-muted">No details are required for this step.</p>}
    </div>
  )
}
