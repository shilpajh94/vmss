import { DynamicField, type DynamicFieldValue } from '../../../../components/dynamic-fields/DynamicField'
import type { FormStep } from '../../../../../domain/entities/form-builder-schema'

interface GenericConfiguredStepProps {
  step: FormStep
  value: Record<string, DynamicFieldValue>
  onChange: (value: Record<string, DynamicFieldValue>) => void
}

/** Renders a registration step whose `key` isn't one of the wizard's six
 * built-in steps — a custom step an admin created in the Form Builder — from
 * its configured fields, so it no longer silently disappears from the
 * wizard (fix-wizard-inactive-steps). `value`/`onChange` are the shared
 * invitation-level `customFieldValues` bucket (`VisitRequestFormState.
 * customFieldValues`) — answers are part of the submission wire contract
 * (add-generic-custom-field-support), not held in step-local state only.
 */
export function GenericConfiguredStep({ step, value, onChange }: GenericConfiguredStepProps) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-h3 text-text">{step.name}</h3>
        {step.description && <p className="text-body text-text-muted">{step.description}</p>}
      </div>
      <div className="flex flex-col gap-4">
        {step.fields.map((field) => (
          <DynamicField
            key={field.id}
            field={field}
            value={value[field.key]}
            onChange={(fieldValue) => onChange({ ...value, [field.key]: fieldValue })}
          />
        ))}
      </div>
    </div>
  )
}
