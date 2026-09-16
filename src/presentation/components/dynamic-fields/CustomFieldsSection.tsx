import { DynamicField, type DynamicFieldValue } from './DynamicField'
import type { FormField } from '../../../domain/entities/form-builder-schema'

interface CustomFieldsSectionProps {
  /** Admin-authored (non-system) fields for one step, at the scope this
   * instance renders for — the whole step for Visit Details/Carried Items/
   * a custom step, or one visitor's/vehicle's own fields for Visitor Info/
   * Vehicle Info. Callers filter to `!field.isSystem` before passing these
   * in; this component doesn't assume anything about which step they came
   * from.
   */
  fields: FormField[]
  value: Record<string, DynamicFieldValue>
  onChange: (value: Record<string, DynamicFieldValue>) => void
}

/** Renders whatever admin-authored fields a step has beyond its own fixed/
 * locked ones, generically — the shared rendering path every step's custom
 * fields go through (add-generic-custom-field-support). Renders nothing
 * when `fields` is empty, so a step with no admin-added fields looks
 * unchanged from before this component existed.
 */
export function CustomFieldsSection({ fields, value, onChange }: CustomFieldsSectionProps) {
  if (fields.length === 0) return null
  return (
    <div className="flex flex-col gap-4">
      {fields.map((field) => (
        <DynamicField
          key={field.id}
          field={field}
          value={value[field.key]}
          onChange={(fieldValue) => onChange({ ...value, [field.key]: fieldValue })}
        />
      ))}
    </div>
  )
}
