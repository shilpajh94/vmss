import { DynamicField } from '../../../../components/dynamic-fields/DynamicField'
import type { FormField } from '../../../../../domain/entities/form-builder-schema'
import type { ConsentFormState } from '../../types'

interface ConsentStepProps {
  /** Active Consent Agreement fields from the resolved branch's published
   * Form Builder configuration. May be genuinely empty once loaded — that's
   * rendered as-is, not masked by a hardcoded default; see `isLoading` for
   * the separate "config hasn't resolved yet" state.
   */
  fields: FormField[]
  isLoading: boolean
  value: ConsentFormState
  onChange: (value: ConsentFormState) => void
  error?: string
}

export function ConsentStep({ fields, isLoading, value, onChange, error }: ConsentStepProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <h3 className="text-h3 text-text">Consent Agreement</h3>
          <p className="text-body text-text-muted">Please read and accept the following terms and conditions before proceeding.</p>
        </div>
        <p className="text-body text-text-muted">Loading…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-h3 text-text">Consent Agreement</h3>
        <p className="text-body text-text-muted">Please read and accept the following terms and conditions before proceeding.</p>
      </div>
      <div className="flex flex-col gap-2">
        {fields.map((field) => (
          <DynamicField
            key={field.id}
            field={field}
            value={value[field.key]}
            onChange={(fieldValue) => onChange({ ...value, [field.key]: Boolean(fieldValue) })}
          />
        ))}
        {fields.length === 0 && <p className="text-body text-text-muted">No consent items are required for this step.</p>}
      </div>
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
