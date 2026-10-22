import { DndContext, MouseSensor, TouchSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useEffect, useState } from 'react'
import { GridIcon, LockIcon, PlusIcon, UnlockIcon, XIcon } from '../../../components/icons'
import { Collapsible } from '../../../components/ui/Collapsible'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { TextareaField } from '../../../components/ui/TextareaField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import {
  CONTENT_ONLY_FIELD_TYPES,
  FIELD_TYPE_CATALOG,
  OPTION_OPTIONAL_FIELD_TYPES,
  OPTION_REQUIRED_FIELD_TYPES,
  TYPE_LOCKED_SYSTEM_FIELD_KEYS,
  fieldTypeLabel,
  typeLockedFieldReason,
} from '../field-type-catalog'
import type {
  ConditionOperator,
  FormField,
  FormFieldType,
  FormFieldUpdateInput,
} from '../../../../domain/entities/form-builder-schema'

interface FieldPropertiesPanelProps {
  field: FormField
  siblingFields: FormField[]
  onSave: (input: FormFieldUpdateInput) => Promise<string | undefined>
}

const NO_CONDITION_VALUE = ''

interface OptionDraftRow {
  id: string
  value: string
}

function toOptionDraftRows(options: string[] | null): OptionDraftRow[] {
  return (options ?? []).map((value) => ({ id: crypto.randomUUID(), value }))
}

function optionsEditorIsShown(fieldType: FormFieldType): boolean {
  return OPTION_REQUIRED_FIELD_TYPES.includes(fieldType) || OPTION_OPTIONAL_FIELD_TYPES.includes(fieldType)
}

interface OptionRowProps {
  row: OptionDraftRow
  disabled: boolean
  onChange: (value: string) => void
  onRemove: () => void
}

function OptionRow({ row, disabled, onChange, onRemove }: OptionRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: row.id,
    disabled,
  })

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-2 ${isDragging ? 'opacity-60' : ''}`}
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        disabled={disabled}
        aria-label="Drag to reorder option"
        className="flex cursor-grab items-center justify-center text-text-faint max-lg:-m-3 max-lg:size-10 disabled:cursor-not-allowed disabled:opacity-40 active:cursor-grabbing"
      >
        <GridIcon className="size-4" />
      </button>
      <input
        value={row.value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="flex-1 rounded-lg border border-border px-3 py-2 text-body text-text focus:outline-none focus:ring-2 focus:ring-secondary-accent disabled:opacity-60"
      />
      {!disabled && (
        <button type="button" onClick={onRemove} aria-label="Remove option" className="text-danger">
          <XIcon className="size-4" />
        </button>
      )}
    </div>
  )
}

export function FieldPropertiesPanel({ field, siblingFields, onSave }: FieldPropertiesPanelProps) {
  const [fieldType, setFieldType] = useState<FormFieldType>(field.fieldType)
  const [label, setLabel] = useState(field.label)
  const [placeholder, setPlaceholder] = useState(field.placeholder ?? '')
  const [description, setDescription] = useState(field.helpText ?? '')
  const [isRequired, setIsRequired] = useState(field.isRequired)
  const [hideLabel, setHideLabel] = useState(field.hideLabel)
  const [isActive, setIsActive] = useState(field.isActive)
  const [minLength, setMinLength] = useState(field.validationRules?.minLength?.toString() ?? '')
  const [maxLength, setMaxLength] = useState(field.validationRules?.maxLength?.toString() ?? '')
  const [conditionFieldKey, setConditionFieldKey] = useState(field.visibilityCondition?.fieldKey ?? NO_CONDITION_VALUE)
  const [conditionOperator, setConditionOperator] = useState<ConditionOperator>(
    field.visibilityCondition?.operator ?? 'equals',
  )
  const [conditionValue, setConditionValue] = useState(field.visibilityCondition?.value ?? '')
  const [width, setWidth] = useState(field.width)
  const [optionRows, setOptionRows] = useState<OptionDraftRow[]>(() => toOptionDraftRows(field.options))
  const [saveError, setSaveError] = useState<string | undefined>(undefined)
  // Session-scoped only — never persisted, never sent to the backend. A
  // locked field's `isLocked` never changes; this just lifts the frontend's
  // own disabled-input guard for label/placeholder/description/options
  // while the admin is actively editing this field.
  const [isUnlockedForEditing, setIsUnlockedForEditing] = useState(false)

  const optionSensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 4 } }),
    // Press-and-hold, so a finger swipe still scrolls the page instead of
    // starting a drag (responsive-layout "Reordering form fields by touch").
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
  )
  const showOptionsEditor = optionsEditorIsShown(fieldType)
  const isContentOnly = CONTENT_ONLY_FIELD_TYPES.includes(fieldType)
  const editableFieldsDisabled = field.isLocked && !isUnlockedForEditing
  // A locked, retypeable field's Field Type control joins the same
  // unlock gate as Label/Placeholder/Description/Options; a
  // TYPE_LOCKED_SYSTEM_FIELD_KEYS field stays disabled regardless of
  // lock/unlock state — its type isn't offered as editable at all.
  const isTypeLockedField = TYPE_LOCKED_SYSTEM_FIELD_KEYS.has(field.key)
  const fieldTypeDisabled = isTypeLockedField || editableFieldsDisabled
  // If this field is already on a type the catalog no longer offers (e.g.
  // one left over from before a type was retired), the picker still needs
  // to show it selected — appending it keeps the <select>'s `value` from
  // pointing at a nonexistent option, without offering it as a new choice
  // anywhere else (it's simply not in FIELD_TYPE_CATALOG).
  const fieldTypeOptions = FIELD_TYPE_CATALOG.some((entry) => entry.type === fieldType)
    ? FIELD_TYPE_CATALOG.map((entry) => ({ value: entry.type, label: entry.label }))
    : [...FIELD_TYPE_CATALOG.map((entry) => ({ value: entry.type, label: entry.label })), { value: fieldType, label: fieldTypeLabel(fieldType) }]

  // Deliberately keyed on `field.id`, not `field` itself: the parent page's
  // 15s background poll (`usePolling` in `use-admin-form-builder-step-editor.ts`)
  // hands this panel a brand-new `field` object on every tick even when
  // nothing about the field actually changed, which — keyed on the object
  // reference — was wiping out whatever the admin had typed/pasted and not
  // yet saved. Re-seeding only when the *selected field itself* changes (a
  // different id) is the correct trigger: a background refresh of the same
  // field's unchanged data should never clobber an in-progress edit.
  useEffect(() => {
    setFieldType(field.fieldType)
    setLabel(field.label)
    setPlaceholder(field.placeholder ?? '')
    setDescription(field.helpText ?? '')
    setIsRequired(field.isRequired)
    setHideLabel(field.hideLabel)
    setIsActive(field.isActive)
    setMinLength(field.validationRules?.minLength?.toString() ?? '')
    setMaxLength(field.validationRules?.maxLength?.toString() ?? '')
    setConditionFieldKey(field.visibilityCondition?.fieldKey ?? NO_CONDITION_VALUE)
    setConditionOperator(field.visibilityCondition?.operator ?? 'equals')
    setConditionValue(field.visibilityCondition?.value ?? '')
    setWidth(field.width)
    setOptionRows(toOptionDraftRows(field.options))
    setSaveError(undefined)
    setIsUnlockedForEditing(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [field.id])

  const reset = () => {
    setFieldType(field.fieldType)
    setLabel(field.label)
    setPlaceholder(field.placeholder ?? '')
    setDescription(field.helpText ?? '')
    setIsRequired(field.isRequired)
    setHideLabel(field.hideLabel)
    setIsActive(field.isActive)
    setMinLength(field.validationRules?.minLength?.toString() ?? '')
    setMaxLength(field.validationRules?.maxLength?.toString() ?? '')
    setConditionFieldKey(field.visibilityCondition?.fieldKey ?? NO_CONDITION_VALUE)
    setConditionOperator(field.visibilityCondition?.operator ?? 'equals')
    setConditionValue(field.visibilityCondition?.value ?? '')
    setWidth(field.width)
    setOptionRows(toOptionDraftRows(field.options))
    setSaveError(undefined)
  }

  const relock = () => {
    reset()
    setIsUnlockedForEditing(false)
  }

  const updateOptionValue = (id: string, value: string) => {
    setOptionRows((current) => current.map((row) => (row.id === id ? { ...row, value } : row)))
  }

  const removeOptionRow = (id: string) => {
    setOptionRows((current) => current.filter((row) => row.id !== id))
  }

  const addOptionRow = () => {
    setOptionRows((current) => [...current, { id: crypto.randomUUID(), value: '' }])
  }

  const handleOptionDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    setOptionRows((current) => {
      const oldIndex = current.findIndex((row) => row.id === active.id)
      const newIndex = current.findIndex((row) => row.id === over.id)
      if (oldIndex === -1 || newIndex === -1) return current
      const reordered = [...current]
      const [moved] = reordered.splice(oldIndex, 1)
      reordered.splice(newIndex, 0, moved)
      return reordered
    })
  }

  const save = async () => {
    const trimmedMin = minLength.trim()
    const trimmedMax = maxLength.trim()

    setSaveError(undefined)
    const errorMessage = await onSave({
      fieldType,
      label: label.trim(),
      placeholder: isContentOnly ? undefined : placeholder.trim() || undefined,
      helpText: description.trim(),
      isRequired: isContentOnly ? false : isRequired,
      hideLabel: isContentOnly ? false : hideLabel,
      isActive,
      width,
      options: showOptionsEditor
        ? optionRows.map((row) => row.value.trim()).filter((value) => value.length > 0)
        : undefined,
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

    if (errorMessage) {
      setSaveError(errorMessage)
      if (errorMessage.toLowerCase().includes('options')) {
        // Revert to the field's last-saved options rather than leaving the
        // rejected (e.g. emptied) draft displayed as if it had been applied.
        setOptionRows(toOptionDraftRows(field.options))
      }
    }
  }

  return (
    <div className="flex w-full flex-col gap-5 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-bold text-text">Field Properties</h2>
          <p className="font-body text-sm text-text-muted">Configuring "{field.label}"</p>
        </div>
        {field.isLocked ? (
          <button
            type="button"
            onClick={() => (isUnlockedForEditing ? relock() : setIsUnlockedForEditing(true))}
            className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 font-body text-[11px] font-bold tracking-wide uppercase ${
              isUnlockedForEditing
                ? 'bg-admin-accent/10 text-admin-accent'
                : 'bg-neutral-subtle text-text-faint'
            }`}
          >
            {isUnlockedForEditing ? <UnlockIcon className="size-3.5" /> : <LockIcon className="size-3.5" />}
            {isUnlockedForEditing ? 'Lock' : 'Unlock to Edit'}
          </button>
        ) : (
          <div className="flex shrink-0 items-center gap-2">
            <span className="font-body text-[11px] font-bold tracking-wide text-text-faint uppercase">
              {isActive ? 'Active' : 'Inactive'}
            </span>
            <ToggleSwitch checked={isActive} onChange={setIsActive} label="" />
          </div>
        )}
      </div>

      <TextField label={isContentOnly ? 'Title' : 'Field Label'} value={label} onChange={setLabel} required disabled={editableFieldsDisabled} />
      {!isContentOnly && (
        <TextField label="Placeholder Text" value={placeholder} onChange={setPlaceholder} disabled={editableFieldsDisabled} />
      )}
      <TextareaField
        label={isContentOnly ? 'Content' : 'Description'}
        value={description}
        onChange={setDescription}
        placeholder="Static text shown to the visitor alongside this field"
        rows={3}
        disabled={editableFieldsDisabled}
      />

      <div>
        <SelectField
          label="Field Type"
          value={fieldType}
          onChange={(value) => setFieldType(value as FormFieldType)}
          disabled={fieldTypeDisabled}
          options={fieldTypeDisabled ? [{ value: fieldType, label: fieldTypeLabel(fieldType) }] : fieldTypeOptions}
        />
        {isTypeLockedField && (
          <p className="mt-1.5 font-body text-xs text-text-muted">{typeLockedFieldReason(field.key)}</p>
        )}
      </div>

      {showOptionsEditor && (
        <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
          <p className="font-body text-sm font-semibold text-text">Options</p>
          {editableFieldsDisabled && (
            <p className="font-body text-xs text-text-muted">
              This field is locked — select "Unlock to Edit" above to change its options.
            </p>
          )}
          <DndContext sensors={optionSensors} collisionDetection={closestCenter} onDragEnd={handleOptionDragEnd}>
            <SortableContext items={optionRows.map((row) => row.id)} strategy={verticalListSortingStrategy}>
              <div className="flex flex-col gap-2">
                {optionRows.map((row) => (
                  <OptionRow
                    key={row.id}
                    row={row}
                    disabled={editableFieldsDisabled}
                    onChange={(value) => updateOptionValue(row.id, value)}
                    onRemove={() => removeOptionRow(row.id)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
          {!editableFieldsDisabled && (
            <button
              type="button"
              onClick={addOptionRow}
              className="flex items-center justify-center gap-2 self-start rounded-lg border border-dashed border-border px-3 py-2 font-body text-xs font-semibold text-admin-accent"
            >
              <PlusIcon className="size-3.5" />
              Add option
            </button>
          )}
        </div>
      )}

      {!isContentOnly && (
        <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
          <p className="font-body text-sm font-semibold text-text">Validation Rules</p>
          <ToggleSwitch checked={isRequired} onChange={setIsRequired} label="Required Field" />
          <ToggleSwitch checked={hideLabel} onChange={setHideLabel} label="Hide Label" />
          {field.isLocked && (
            <p className="font-body text-xs text-text-muted">
              This field's required/active state is locked and cannot be changed, even when unlocked for editing.
            </p>
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextField label="Min Length" value={minLength} onChange={setMinLength} type="number" />
            <TextField label="Max Length" value={maxLength} onChange={setMaxLength} type="number" />
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
        <p className="font-body text-sm font-semibold text-text">Conditional Visibility</p>
        <SelectField
          label="Show this field when:"
          value={conditionFieldKey}
          onChange={setConditionFieldKey}
          placeholderSelectable
          placeholder="Always shown"
          options={siblingFields.filter((f) => f.id !== field.id).map((f) => ({ value: f.key, label: f.label }))}
        />
        <Collapsible open={conditionFieldKey !== NO_CONDITION_VALUE} closedClassName="-mt-3" className="flex flex-col gap-3">
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
        </Collapsible>
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

      {saveError && <p className="font-body text-sm text-danger">{saveError}</p>}

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => void save()}
          className="flex-1 rounded-lg bg-admin-accent px-4 py-2.5 font-body text-sm font-semibold text-on-accent"
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
