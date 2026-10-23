import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { LayersIcon, LockIcon, TrashIcon } from '../../../components/icons'
import { Collapsible } from '../../../components/ui/Collapsible'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import type {
  ConditionOperator,
  FormField,
  FormFieldGroup,
  FormFieldGroupUpdateInput,
} from '../../../../domain/entities/form-builder-schema'

const NO_CONDITION_VALUE = ''

// The one seeded group whose instance count is governed entirely by
// registrationType (individual/group) elsewhere, not an admin-configurable
// range — mirrors `form_builder/service.py::_NO_INSTANCE_RANGE_SYSTEM_GROUP_KEYS`.
// The seeded "vehicles" group is also locked+repeatable but, unlike this
// one, its min/max IS admin-editable.
const NO_INSTANCE_RANGE_GROUP_KEYS = new Set(['visitors'])

interface GroupCardProps {
  group: FormFieldGroup
  fieldCount: number
  /** Every other field on the group's step, used to populate the "Show
   * this group when" watched-field picker — the group's own member fields
   * are excluded client-side (a group can't be gated on one of its own
   * fields; the backend rejects it too, see `form_builder/service.py`'s
   * self-reference guard). */
  siblingFields: FormField[]
  onSaveProperties: (input: FormFieldGroupUpdateInput) => Promise<string | undefined>
  onDelete: () => void
  /** Rendered next to the group name only for a draggable (non-locked)
   * group — see `SortableGroupCard`. */
  dragHandle?: ReactNode
}

export function GroupCard({ group, fieldCount, siblingFields, onSaveProperties, onDelete, dragHandle }: GroupCardProps) {
  const [isRepeatable, setIsRepeatable] = useState(group.isRepeatable)
  const [minInstances, setMinInstances] = useState(group.minInstances?.toString() ?? '')
  const [maxInstances, setMaxInstances] = useState(group.maxInstances?.toString() ?? '')
  const [conditionFieldKey, setConditionFieldKey] = useState(group.visibilityCondition?.fieldKey ?? NO_CONDITION_VALUE)
  const [conditionOperator, setConditionOperator] = useState<ConditionOperator>(
    group.visibilityCondition?.operator ?? 'equals',
  )
  const [conditionValue, setConditionValue] = useState(group.visibilityCondition?.value ?? '')
  const [saveError, setSaveError] = useState<string | undefined>(undefined)

  const showInstanceRange = !NO_INSTANCE_RANGE_GROUP_KEYS.has(group.key)
  const pickableFields = siblingFields.filter((f) => f.groupId !== group.id)

  // Re-seed only when the group itself changes (a different id) — the same
  // "don't clobber an in-progress edit on a background poll tick" guard
  // `FieldPropertiesPanel` uses for fields.
  useEffect(() => {
    setIsRepeatable(group.isRepeatable)
    setMinInstances(group.minInstances?.toString() ?? '')
    setMaxInstances(group.maxInstances?.toString() ?? '')
    setConditionFieldKey(group.visibilityCondition?.fieldKey ?? NO_CONDITION_VALUE)
    setConditionOperator(group.visibilityCondition?.operator ?? 'equals')
    setConditionValue(group.visibilityCondition?.value ?? '')
    setSaveError(undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [group.id])

  const saveRepeatable = async (nextRepeatable: boolean) => {
    setIsRepeatable(nextRepeatable)
    const errorMessage = await onSaveProperties({ isRepeatable: nextRepeatable })
    if (errorMessage) {
      setIsRepeatable(group.isRepeatable)
      setSaveError(errorMessage)
    } else {
      setSaveError(undefined)
    }
  }

  const saveInstanceRange = async () => {
    const errorMessage = await onSaveProperties({
      minInstances: minInstances.trim() ? Number(minInstances) : null,
      maxInstances: maxInstances.trim() ? Number(maxInstances) : null,
    })
    if (errorMessage) {
      setMinInstances(group.minInstances?.toString() ?? '')
      setMaxInstances(group.maxInstances?.toString() ?? '')
    }
    setSaveError(errorMessage)
  }

  // Same save-immediately convention as `saveRepeatable`/`saveInstanceRange`
  // above — there's no standalone "Save" button on this card, unlike
  // `FieldPropertiesPanel`. A rejection (dangling/self-referencing
  // `fieldKey`) reverts the three condition fields to the group's
  // last-saved condition and surfaces the message via the same inline
  // `saveError` the min/max range uses.
  const saveCondition = async (nextFieldKey: string, nextOperator: ConditionOperator, nextValue: string) => {
    const errorMessage = await onSaveProperties({
      visibilityCondition:
        nextFieldKey === NO_CONDITION_VALUE ? null : { fieldKey: nextFieldKey, operator: nextOperator, value: nextValue },
    })
    if (errorMessage) {
      setConditionFieldKey(group.visibilityCondition?.fieldKey ?? NO_CONDITION_VALUE)
      setConditionOperator(group.visibilityCondition?.operator ?? 'equals')
      setConditionValue(group.visibilityCondition?.value ?? '')
    }
    setSaveError(errorMessage)
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          {dragHandle}
          <LayersIcon className="size-4 shrink-0 text-admin-accent" />
          {group.isLocked && <LockIcon className="size-3.5 shrink-0 text-text-faint" />}
          <span className="truncate font-body text-sm font-semibold text-text">{group.name}</span>
          <span className="shrink-0 rounded-full bg-bg px-2 py-0.5 font-body text-[11px] font-medium text-text-muted">
            {fieldCount} field{fieldCount === 1 ? '' : 's'}
          </span>
        </div>
        {!group.isLocked && (
          <button
            type="button"
            onClick={onDelete}
            aria-label="Delete group"
            className="flex size-10 shrink-0 items-center justify-center rounded-lg text-danger lg:size-8"
          >
            <TrashIcon className="size-4" />
          </button>
        )}
      </div>

      <ToggleSwitch
        checked={isRepeatable}
        onChange={(checked) => void saveRepeatable(checked)}
        label={group.isLocked ? 'Repeatable (locked — always on)' : 'Repeatable (visitors can add multiple)'}
      />
      {group.isLocked && !showInstanceRange && (
        <p className="font-body text-xs text-text-muted">
          This group's instance count is governed by Registration Type, not a configurable range.
        </p>
      )}

      <Collapsible open={isRepeatable && showInstanceRange} closedClassName="-mt-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Min Instances"
            value={minInstances}
            onChange={setMinInstances}
            onBlur={() => void saveInstanceRange()}
            type="number"
            placeholder="No minimum"
          />
          <TextField
            label="Max Instances"
            value={maxInstances}
            onChange={setMaxInstances}
            onBlur={() => void saveInstanceRange()}
            type="number"
            placeholder="No maximum"
          />
        </div>
      </Collapsible>

      <div className="flex flex-col gap-3 rounded-lg border border-border p-3">
        <p className="font-body text-xs font-semibold text-text">Conditional Visibility</p>
        <SelectField
          label="Show this group when:"
          value={conditionFieldKey}
          onChange={(value) => {
            setConditionFieldKey(value)
            void saveCondition(value, conditionOperator, conditionValue)
          }}
          placeholderSelectable
          placeholder="Always shown"
          options={pickableFields.map((f) => ({ value: f.key, label: f.label }))}
        />
        <Collapsible open={conditionFieldKey !== NO_CONDITION_VALUE} closedClassName="-mt-3" className="flex flex-col gap-3">
          <SelectField
            label="Condition is:"
            value={conditionOperator}
            onChange={(value) => {
              const nextOperator = value as ConditionOperator
              setConditionOperator(nextOperator)
              void saveCondition(conditionFieldKey, nextOperator, conditionValue)
            }}
            options={[
              { value: 'equals', label: 'Equals' },
              { value: 'not_equals', label: 'Not Equals' },
            ]}
          />
          <TextField
            label="Value"
            value={conditionValue}
            onChange={setConditionValue}
            onBlur={() => void saveCondition(conditionFieldKey, conditionOperator, conditionValue)}
            placeholder="e.g. group"
            maxLength={255}
          />
        </Collapsible>
      </div>

      {saveError && <p className="font-body text-xs text-danger">{saveError}</p>}
    </div>
  )
}
