import type { DynamicFieldValue } from './DynamicField'
import type { EffectiveFormFieldGroup, EffectiveFormStep, VisibilityCondition } from '../../../domain/entities/form-builder-schema'
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

/** A group's first `file_upload`-typed field, addressed by `fieldKeys`
 * against the step's own field list — mirrors VMSS_API's
 * `invitations/service.py::_group_field_file_key` exactly: only that one
 * field is ever eligible to travel as a multipart file. */
function groupFileFieldKey(group: EffectiveFormFieldGroup, stepFields: EffectiveFormStep['fields']): string | undefined {
  return group.fieldKeys
    .map((fieldKey) => stepFields.find((field) => field.key === fieldKey))
    .find((field) => field?.fieldType === 'file_upload')?.key
}

/** Pulls each admin-defined field group's `file_upload` field answer out of
 * `groupValues` and resolves it to the real `File` `uploadFile` registered
 * in `fileRegistry` (add-group-field-file-upload). The backend only ever
 * accepts that field's answer as a multipart `groupFieldFiles[<groupKey>]`
 * list, order-matched to that group's `groupValues[<groupKey>]` instances —
 * the same "list, order-matched to instances" convention already used for
 * `visitorIdProofFiles`/`visitor_id_proof_files` — and rejects the instance
 * outright (422) if the field is still present as a JSON value, so it must
 * be stripped from every instance here rather than merely left alongside
 * the resolved file (see VMSS_API's `docs/features/invitations.md`
 * "Repeatable group file uploads").
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
      const fileFieldKey = groupFileFieldKey(group, step.fields)
      const instances = groupValues[group.key]
      if (!fileFieldKey || !instances || instances.length === 0) continue

      const files: File[] = []
      sanitizedGroupValues[group.key] = instances.map((instance) => {
        if (!(fileFieldKey in instance)) return instance
        const fileValue = instance[fileFieldKey]
        if (fileValue !== undefined && typeof fileValue === 'object' && !Array.isArray(fileValue)) {
          const file = fileRegistry.get(fileValue.fileRef)
          if (file) files.push(file)
        }
        const sanitizedInstance: GroupInstance = { ...instance }
        delete sanitizedInstance[fileFieldKey]
        return sanitizedInstance
      })
      if (files.length > 0) groupFieldFiles[group.key] = files
    }
  }

  return { sanitizedGroupValues, groupFieldFiles }
}
