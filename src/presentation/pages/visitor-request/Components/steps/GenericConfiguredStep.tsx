import { DynamicField, type DynamicFieldValue } from '../../../../components/dynamic-fields/DynamicField'
import { resolveGroupFlatValues } from '../../../../components/dynamic-fields/field-group-visibility'
import { FieldGroupsSection } from '../../../../components/dynamic-fields/FieldGroupsSection'
import type { GroupInstance } from '../../../../components/dynamic-fields/RepeatableFieldGroup'
import type { EffectiveFormStep } from '../../../../../domain/entities/form-builder-schema'

interface GenericConfiguredStepProps {
  step: EffectiveFormStep
  value: Record<string, DynamicFieldValue>
  onChange: (value: Record<string, DynamicFieldValue>) => void
  /** This step's admin-defined field groups' current instances, keyed by
   * group key (`VisitRequestFormState.groupValues` /
   * `StaffVisitRequestFormState.groupValues`) — add-repeatable-field-groups.
   * A group absent from this map renders with zero instances. */
  groupValues: Record<string, GroupInstance[]>
  onGroupValuesChange: (groupValues: Record<string, GroupInstance[]>) => void
}

/** Renders a registration step whose `key` isn't one of the wizard's six
 * built-in steps — a custom step an admin created in the Form Builder — from
 * its configured fields, so it no longer silently disappears from the
 * wizard (fix-wizard-inactive-steps). `value`/`onChange` are the shared
 * invitation-level `customFieldValues` bucket (`VisitRequestFormState.
 * customFieldValues`) — answers are part of the submission wire contract
 * (add-generic-custom-field-support), not held in step-local state only.
 *
 * A field belonging to one of the step's groups (`field.groupId` set) is
 * excluded from the flat list below and rendered instead once per group, in
 * the group's `orderIndex` order (add-repeatable-field-groups) — an
 * ungrouped field (`groupId: null`) renders exactly as before. A
 * repeatable group renders through `RepeatableFieldGroup`'s add/edit/
 * remove-instance UI; a non-repeatable group is always exactly one
 * instance (`specs/form-builder/spec.md` "A Field Group May Be Marked
 * Repeatable..."), so it renders as a plain labeled fieldset instead —
 * no add/remove affordance — with its single instance stored as
 * `groupValues[key][0]` so the wire shape (`groupValues[key]: object[]`)
 * stays uniform for every group regardless of repeatability.
 *
 * A group's own `visibilityCondition` (add-conditional-field-groups) is
 * evaluated against the step's currently-known flat values before deciding
 * whether to render it at all — see `FieldGroupsSection`/`isGroupVisible`.
 */
export function GenericConfiguredStep({ step, value, onChange, groupValues, onGroupValuesChange }: GenericConfiguredStepProps) {
  const groupedFieldKeys = new Set(step.groups.flatMap((group) => group.fieldKeys))
  const ungroupedFields = step.fields.filter((field) => !groupedFieldKeys.has(field.key))

  // A condition can only ever watch a field on the same step — see
  // `resolveGroupFlatValues`'s own comment for what this can and can't
  // resolve.
  const flatValues: Record<string, DynamicFieldValue> = resolveGroupFlatValues(step.groups, groupValues, value)

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-h3 text-text">{step.name}</h3>
        {step.description && <p className="text-body text-text-muted">{step.description}</p>}
      </div>
      <div className="flex flex-col gap-4">
        {ungroupedFields.map((field) => (
          <DynamicField
            key={field.id}
            field={field}
            value={value[field.key]}
            onChange={(fieldValue) => onChange({ ...value, [field.key]: fieldValue })}
          />
        ))}
      </div>
      <FieldGroupsSection
        groups={step.groups}
        fields={step.fields}
        flatValues={flatValues}
        groupValues={groupValues}
        onGroupValuesChange={onGroupValuesChange}
      />
    </div>
  )
}
