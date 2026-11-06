import type { DynamicFieldValue } from './DynamicField'
import type { EffectiveFormFieldGroup, EffectiveFormStep, FormField, VisibilityCondition } from '../../../domain/entities/form-builder-schema'
import type { GroupAnswer } from '../../../domain/entities/form-field-answer-schema'
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

export interface ExtractedGroupFieldFiles {
  sanitizedGroupValues: Record<string, GroupInstance[]>
  groupFieldFiles: Record<string, File[]>
}

/** Every field actually belonging to `group`, per the field's own
 * authoritative `groupId` — NOT resolved via `group.fieldKeys` matched
 * against the step's full field list, since a key can collide with an
 * ungrouped field or another group's field on the same step (that
 * ambiguity caused `toGroupAnswers` to attribute a foreign field's id to
 * this group; see restructure-walkin-payload-by-field-id). */
function groupMemberFields(group: EffectiveFormFieldGroup, stepFields: EffectiveFormStep['fields']): FormField[] {
  return stepFields.filter((field) => field.groupId === group.id)
}

/** Pulls every `file_upload` field's answer of each admin-defined field group
 * out of `groupValues` and resolves it to the real `File` `uploadFile`
 * registered in `fileRegistry`. The backend accepts these as multipart
 * `groupFieldFiles[<fieldId>]` lists — one key per file field, one file per
 * instance, order-matched to that group's instances (the legacy
 * `groupFieldFiles[<groupId>]` key only maps to the group's FIRST file field,
 * so it is deliberately not used; see VMSS_API's `docs/features/invitations.md`
 * "Multiple file fields in one group"). The backend also rejects an instance
 * outright (422) if a file field is still present as a JSON value, so each is
 * stripped from every instance here. `sanitizedGroupValues` stays keyed by
 * the group's `key` (internal wizard state); the returned `groupFieldFiles`
 * map is keyed by the file field's `id` (the wire contract's part key).
 */
export function extractGroupFieldFiles(
  steps: EffectiveFormStep[],
  groupValues: Record<string, GroupInstance[]>,
  fileRegistry: Map<string, File>,
): ExtractedGroupFieldFiles {
  const sanitizedGroupValues: Record<string, GroupInstance[]> = { ...groupValues }
  const groupFieldFiles: Record<string, File[]> = {}

  for (const step of steps) {
    for (const group of step.groups) {
      const fileFields = groupMemberFields(group, step.fields).filter((field) => field.fieldType === 'file_upload')
      const instances = groupValues[group.key]
      if (fileFields.length === 0 || !instances || instances.length === 0) continue

      for (const fileField of fileFields) {
        const files: File[] = []
        sanitizedGroupValues[group.key] = sanitizedGroupValues[group.key].map((instance) => {
          if (!(fileField.key in instance)) return instance
          const fileValue = instance[fileField.key]
          if (fileValue !== undefined && typeof fileValue === 'object' && !Array.isArray(fileValue)) {
            const file = fileRegistry.get(fileValue.fileRef)
            if (file) files.push(file)
          }
          const sanitizedInstance: GroupInstance = { ...instance }
          delete sanitizedInstance[fileField.key]
          return sanitizedInstance
        })
        if (files.length > 0) groupFieldFiles[fileField.id] = files
      }
    }
  }

  return { sanitizedGroupValues, groupFieldFiles }
}

/** Converts every admin-defined field group's current instances (internal
 * wizard state, keyed by `key`) into the wire contract's `groups` array,
 * addressed by `groupId`/`fieldId` (restructure-walkin-payload-by-field-id).
 * A group with zero instances is omitted entirely. */
export function toGroupAnswers(steps: EffectiveFormStep[], groupValues: Record<string, GroupInstance[]>): GroupAnswer[] {
  const answers: GroupAnswer[] = []
  for (const step of steps) {
    for (const group of step.groups) {
      const instances = groupValues[group.key]
      if (!instances || instances.length === 0) continue
      const groupFields = groupMemberFields(group, step.fields)
      answers.push({
        groupId: group.id,
        instances: instances.map((instance) =>
          groupFields.filter((field) => field.key in instance).map((field) => ({ fieldId: field.id, value: instance[field.key] })),
        ),
      })
    }
  }
  return answers
}

/** Key under which a repeatable group's min-instances error is stored in a
 * wizard's `errors` map and read back by `FieldGroupsSection`. */
export const groupErrorKey = (groupKey: string) => `group:${groupKey}`

/** Next-click validation for a step's repeatable groups: every *visible*
 * repeatable group must hold at least its `minInstances`. Returns errors
 * keyed by `groupErrorKey`, merged by each wizard's `validateStep`. */
export function validateGroupMinimums(
  groups: EffectiveFormFieldGroup[],
  groupValues: Record<string, GroupInstance[]>,
  seedValues: Record<string, DynamicFieldValue>,
): Record<string, string> {
  const errors: Record<string, string> = {}
  const flatValues = resolveGroupFlatValues(groups, groupValues, seedValues)
  for (const group of groups) {
    if (!group.isRepeatable || group.minInstances === null) continue
    if (!isGroupVisible(group.visibilityCondition, flatValues)) continue
    if ((groupValues[group.key]?.length ?? 0) < group.minInstances) {
      errors[groupErrorKey(group.key)] = `At least ${group.minInstances} ${group.name.toLowerCase()} required.`
    }
  }
  return errors
}
