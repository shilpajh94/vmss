import { CustomFieldsSection } from '../../../../components/dynamic-fields/CustomFieldsSection'
import { DynamicField, type DynamicFieldValue } from '../../../../components/dynamic-fields/DynamicField'
import { RepeatableFieldGroup, type GroupInstance } from '../../../../components/dynamic-fields/RepeatableFieldGroup'
import type { EffectiveFormStep, VisibilityCondition } from '../../../../../domain/entities/form-builder-schema'

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
 * whether to render it at all — see `isGroupVisible` below.
 */
export function GenericConfiguredStep({ step, value, onChange, groupValues, onGroupValuesChange }: GenericConfiguredStepProps) {
  const groupedFieldKeys = new Set(step.groups.flatMap((group) => group.fieldKeys))
  const ungroupedFields = step.fields.filter((field) => !groupedFieldKeys.has(field.key))
  const orderedGroups = [...step.groups].sort((a, b) => a.orderIndex - b.orderIndex)

  // A condition can only ever watch a field on the same step. The only
  // fields this component can resolve a single, unambiguous current value
  // for are: an ungrouped field (`value`) and a field belonging to a
  // *non-repeatable* group (its one instance, `groupValues[key][0]`). A
  // field inside a *repeatable* group has zero-to-many instances, so there
  // is no single current value to compare against — a group conditioned on
  // such a field is a known limitation (see file-level comment) and simply
  // won't resolve to visible.
  const flatValues: Record<string, DynamicFieldValue> = { ...value }
  for (const otherGroup of step.groups) {
    if (otherGroup.isRepeatable) continue
    const singleInstance = groupValues[otherGroup.key]?.[0]
    if (!singleInstance) continue
    for (const fieldKey of otherGroup.fieldKeys) {
      if (fieldKey in singleInstance) flatValues[fieldKey] = singleInstance[fieldKey]
    }
  }

  const setGroupInstances = (groupKey: string, instances: GroupInstance[]) => {
    onGroupValuesChange({ ...groupValues, [groupKey]: instances })
  }

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
      {orderedGroups.map((group) => {
        if (!isGroupVisible(group.visibilityCondition, flatValues)) return null

        const groupFields = group.fieldKeys
          .map((fieldKey) => step.fields.find((field) => field.key === fieldKey))
          .filter((field): field is (typeof step.fields)[number] => field !== undefined)

        if (!group.isRepeatable) {
          const singleInstance = groupValues[group.key]?.[0] ?? {}
          return (
            <div key={group.id} className="flex flex-col gap-4 rounded-lg border border-border-subtle bg-surface p-4">
              <h3 className="text-h3 text-text">{group.name}</h3>
              <CustomFieldsSection
                fields={groupFields}
                value={singleInstance}
                onChange={(instance) => setGroupInstances(group.key, [instance])}
              />
            </div>
          )
        }

        return (
          <RepeatableFieldGroup
            key={group.id}
            groupName={group.name}
            fields={groupFields}
            minInstances={group.minInstances}
            maxInstances={group.maxInstances}
            instances={groupValues[group.key] ?? []}
            onChange={(instances) => setGroupInstances(group.key, instances)}
          />
        )
      })}
    </div>
  )
}

/** Pure evaluator for a `FormFieldGroup`'s `visibilityCondition`
 * (add-conditional-field-groups) — `null` means always visible. Plain
 * string comparison against the watched field's current value, same
 * `equals`/`not_equals` semantics `FormFieldGroupCreate`/`Update`'s schema
 * documents; a value the frontend can't currently resolve (see the
 * `flatValues` comment above) is treated as an empty string, matching how
 * an unanswered field would compare. Scoped to this file since nothing
 * else evaluates a `VisibilityCondition` at runtime yet. */
function isGroupVisible(
  condition: VisibilityCondition | null,
  values: Record<string, DynamicFieldValue>,
): boolean {
  if (!condition) return true
  const actual = values[condition.fieldKey]
  const matches = (Array.isArray(actual) ? actual.join(',') : (actual ?? '').toString()) === condition.value
  return condition.operator === 'equals' ? matches : !matches
}
