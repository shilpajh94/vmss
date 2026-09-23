import { CustomFieldsSection } from './CustomFieldsSection'
import type { DynamicFieldValue } from './DynamicField'
import { isGroupVisible } from './field-group-visibility'
import { RepeatableFieldGroup, type GroupInstance } from './RepeatableFieldGroup'
import type { EffectiveFormFieldGroup, FormField } from '../../../domain/entities/form-builder-schema'

interface FieldGroupsSectionProps {
  /** The step's groups to render, in `orderIndex` order — a group whose
   * `visibilityCondition` doesn't currently resolve true renders nothing. */
  groups: EffectiveFormFieldGroup[]
  /** Every field on the step, used to resolve each group's `fieldKeys`. */
  fields: FormField[]
  /** Current values a group's `visibilityCondition` is checked against —
   * see `resolveGroupFlatValues`. */
  flatValues: Record<string, DynamicFieldValue>
  groupValues: Record<string, GroupInstance[]>
  onGroupValuesChange: (groupValues: Record<string, GroupInstance[]>) => void
}

/** Renders a step's admin-defined field groups (add-repeatable-field-groups /
 * add-conditional-field-groups): a repeatable group through
 * `RepeatableFieldGroup`'s add/edit/remove-instance UI, a non-repeatable
 * group as a plain labeled fieldset with its single instance stored as
 * `groupValues[key][0]` (so the wire shape, `groupValues[key]: object[]`,
 * stays uniform regardless of repeatability) — gated on `isGroupVisible`.
 * Shared by `GenericConfiguredStep` (a custom step's own groups) and the
 * Visitor Info step (its built-in step's groups), which otherwise have no
 * component in common.
 */
export function FieldGroupsSection({ groups, fields, flatValues, groupValues, onGroupValuesChange }: FieldGroupsSectionProps) {
  const orderedGroups = [...groups].sort((a, b) => a.orderIndex - b.orderIndex)

  const setGroupInstances = (groupKey: string, instances: GroupInstance[]) => {
    onGroupValuesChange({ ...groupValues, [groupKey]: instances })
  }

  return (
    <>
      {orderedGroups.map((group) => {
        if (!isGroupVisible(group.visibilityCondition, flatValues)) return null

        const groupFields = group.fieldKeys
          .map((fieldKey) => fields.find((field) => field.key === fieldKey))
          .filter((field): field is FormField => field !== undefined)

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
    </>
  )
}
