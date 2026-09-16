import { useEffect, useState } from 'react'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import { fieldTypeLabel } from '../field-type-catalog'
import type {
  ConditionOperator,
  FormField,
  FormFieldUpdateInput,
} from '../../../../domain/entities/form-builder-schema'

interface FieldPropertiesPanelProps {
  field: FormField
  siblingFields: FormField[]
  onSave: (input: FormFieldUpdateInput) => void
}

const NO_CONDITION_VALUE = '__none__'

export function FieldPropertiesPanel({ field, siblingFields, onSave }: FieldPropertiesPanelProps) {
  const [label, setLabel] = useState(field.label)
  const [placeholder, setPlaceholder] = useState(field.placeholder ?? '')
  const [isRequired, setIsRequired] = useState(field.isRequired)
  const [isActive, setIsActive] = useState(field.isActive)
  const [minLength, setMinLength] = useState(field.validationRules?.minLength?.toString() ?? '')
  const [maxLength, setMaxLength] = useState(field.validationRules?.maxLength?.toString() ?? '')
  const [conditionFieldKey, setConditionFieldKey] = useState(field.visibilityCondition?.fieldKey ?? NO_CONDITION_VALUE)
  const [conditionOperator, setConditionOperator] = useState<ConditionOperator>(
    field.visibilityCondition?.operator ?? 'equals',
  )
  const [conditionValue, setConditionValue] = useState(field.visibilityCondition?.value ?? '')
  const [width, setWidth] = useState(field.width)

  useEffect(() => {
    setLabel(field.label)
    setPlaceholder(field.placeholder ?? '')
    setIsRequired(field.isRequired)
    setIsActive(field.isActive)
    setMinLength(field.validationRules?.minLength?.toString() ?? '')
    setMaxLength(field.validationRules?.maxLength?.toString() ?? '')
    setConditionFieldKey(field.visibilityCondition?.fieldKey ?? NO_CONDITION_VALUE)
    setConditionOperator(field.visibilityCondition?.operator ?? 'equals')
    setConditionValue(field.visibilityCondition?.value ?? '')
    setWidth(field.width)
  }, [field])

  const reset = () => {
    setLabel(field.label)
    setPlaceholder(field.placeholder ?? '')
    setIsRequired(field.isRequired)
    setIsActive(field.isActive)
    setMinLength(field.validationRules?.minLength?.toString() ?? '')
    setMaxLength(field.validationRules?.maxLength?.toString() ?? '')
    setConditionFieldKey(field.visibilityCondition?.fieldKey ?? NO_CONDITION_VALUE)
    setConditionOperator(field.visibilityCondition?.operator ?? 'equals')
    setConditionValue(field.visibilityCondition?.value ?? '')
    setWidth(field.width)
  }

  const save = () => {
    const trimmedMin = minLength.trim()
    const trimmedMax = maxLength.trim()

    onSave({
      label: label.trim(),
      placeholder: placeholder.trim() || undefined,
      isRequired,
      isActive,
      width,
      validationRules:
        trimmedMin || trimmedMax
          ? {
              minLength: trimmedMin ? Number(trimmedMin) : undefined,
              maxLength: trimmedMax ? Number(trimmedMax) : undefined,
            }
          : null,
      visibilityCondition:
        conditionFieldKey === NO_CONDITION_VALUE
          ? null
          : { fieldKey: conditionFieldKey, operator: conditionOperator, value: conditionValue },
    })
  }

  return (
    <div className="flex w-full flex-col gap-5 rounded-2xl border border-border bg-surface p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-bold text-text">Field Properties</h2>
          <p className="font-body text-sm text-text-muted">Configuring "{field.label}"</p>
        </div>
        {field.isLocked ? (
          <span className="shrink-0 rounded-full bg-neutral-subtle px-3 py-1 font-body text-[11px] font-bold tracking-wide text-text-faint uppercase">
            Locked
          </span>
        ) : (
          <div className="flex shrink-0 items-center gap-2">
            <span className="font-body text-[11px] font-bold tracking-wide text-text-faint uppercase">
              {isActive ? 'Active' : 'Inactive'}
            </span>
            <ToggleSwitch checked={isActive} onChange={setIsActive} label="" />
          </div>
        )}
      </div>

      <TextField label="Field Label" value={label} onChange={setLabel} required disabled={field.isLocked} />
      <TextField label="Placeholder Text" value={placeholder} onChange={setPlaceholder} disabled={field.isLocked} />

      <SelectField
        label="Field Type"
        value={field.fieldType}
        onChange={() => {}}
        disabled
        options={[{ value: field.fieldType, label: fieldTypeLabel(field.fieldType) }]}
      />

      <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
        <p className="font-body text-sm font-semibold text-text">Validation Rules</p>
        <ToggleSwitch checked={isRequired} onChange={setIsRequired} label="Required Field" />
        {field.isLocked && (
          <p className="font-body text-xs text-text-muted">This field is locked and always active/required.</p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Min Length" value={minLength} onChange={setMinLength} type="number" />
          <TextField label="Max Length" value={maxLength} onChange={setMaxLength} type="number" />
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
        <p className="font-body text-sm font-semibold text-text">Conditional Visibility</p>
        <SelectField
          label="Show this field when:"
          value={conditionFieldKey}
          onChange={setConditionFieldKey}
          placeholderSelectable
          placeholder="Always shown"
          options={[
            { value: NO_CONDITION_VALUE, label: 'Always shown' },
            ...siblingFields.filter((f) => f.id !== field.id).map((f) => ({ value: f.key, label: f.label })),
          ]}
        />
        {conditionFieldKey !== NO_CONDITION_VALUE && (
          <>
            <SelectField
              label="Condition is:"
              value={conditionOperator}
              onChange={(value) => setConditionOperator(value as ConditionOperator)}
              options={[
                { value: 'equals', label: 'Equals' },
                { value: 'not_equals', label: 'Not Equals' },
              ]}
            />
            <TextField label="Value" value={conditionValue} onChange={setConditionValue} placeholder="e.g. group" />
          </>
        )}
      </div>

      <div>
        <p className="mb-2 font-body text-sm font-semibold text-text">Field Width</p>
        <div className="flex gap-2">
          {(['half', 'full'] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setWidth(option)}
              className={`flex-1 rounded-lg border px-3 py-2 font-body text-sm font-semibold capitalize ${
                width === option ? 'border-admin-accent bg-admin-accent/10 text-admin-accent' : 'border-border text-text'
              }`}
            >
              {option} Width
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          className="flex-1 rounded-lg bg-admin-accent px-4 py-2.5 font-body text-sm font-semibold text-white"
        >
          Save Properties
        </button>
        <button
          type="button"
          onClick={reset}
          className="rounded-lg border border-border bg-bg px-4 py-2.5 font-body text-sm font-semibold text-text"
        >
          Reset
        </button>
      </div>
    </div>
  )
}
