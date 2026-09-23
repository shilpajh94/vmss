import type { DynamicFieldValue } from './DynamicField'
import type { EffectiveFormFieldGroup, VisibilityCondition } from '../../../domain/entities/form-builder-schema'
import type { GroupInstance } from './RepeatableFieldGroup'

/** Pure evaluator for a `FormFieldGroup`'s `visibilityCondition`
 * (add-conditional-field-groups) — `null` means always visible. Plain
 * string comparison against the watched field's current value, same
 * `equals`/`not_equals` semantics `FormFieldGroupCreate`/`Update`'s schema
 * documents; a value the frontend can't currently resolve is treated as an
 * empty string, matching how an unanswered field would compare. Shared by
 * every place that renders a step's field groups (`GenericConfiguredStep`,
 * the Visitor Info step's own groups) so a group's condition is honored
 * consistently regardless of which step it lives on.
 */
export function isGroupVisible(condition: VisibilityCondition | null, values: Record<string, DynamicFieldValue>): boolean {
  if (!condition) return true
  const actual = values[condition.fieldKey]
  const matches = (Array.isArray(actual) ? actual.join(',') : (actual ?? '').toString()) === condition.value
  return condition.operator === 'equals' ? matches : !matches
}

/** Builds the flat value map a step's group conditions are evaluated
 * against: `seedValues` (whatever the caller already knows — an ungrouped
 * field's answers, a system field like `registration_type`) plus, for every
 * *non-repeatable* group on the step, that group's single instance's
 * answers. A condition can only ever watch a field on the same step, and a
 * field inside a *repeatable* group has zero-to-many instances — there's no
 * single current value to compare against, so a group conditioned on such a
 * field is a known limitation and simply won't resolve to visible.
 */
export function resolveGroupFlatValues(
  groups: EffectiveFormFieldGroup[],
  groupValues: Record<string, GroupInstance[]>,
  seedValues: Record<string, DynamicFieldValue>,
): Record<string, DynamicFieldValue> {
  const flatValues: Record<string, DynamicFieldValue> = { ...seedValues }
  for (const group of groups) {
    if (group.isRepeatable) continue
    const singleInstance = groupValues[group.key]?.[0]
    if (!singleInstance) continue
    for (const fieldKey of group.fieldKeys) {
      if (fieldKey in singleInstance) flatValues[fieldKey] = singleInstance[fieldKey]
    }
  }
  return flatValues
}
