import { useState } from 'react'
import { Modal } from '../../../components/ui/Modal'
import { TextareaField } from '../../../components/ui/TextareaField'
import { TextField } from '../../../components/ui/TextField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import { FIELD_TYPE_CATALOG, OPTION_REQUIRED_FIELD_TYPES } from '../field-type-catalog'
import type { FormFieldCreateInput, FormFieldType } from '../../../../domain/entities/form-builder-schema'

interface AddFieldModalProps {
  isOpen: boolean
  onClose: () => void
  onCreate: (input: FormFieldCreateInput) => void
}

function slugify(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

export function AddFieldModal({ isOpen, onClose, onCreate }: AddFieldModalProps) {
  const [fieldType, setFieldType] = useState<FormFieldType>('text')
  const [label, setLabel] = useState('')
  const [placeholder, setPlaceholder] = useState('')
  const [description, setDescription] = useState('')
  const [isRequired, setIsRequired] = useState(true)
  const [optionsText, setOptionsText] = useState('')

  const requiresOptions = OPTION_REQUIRED_FIELD_TYPES.includes(fieldType)
  const isContentOnly = fieldType === 'static_text'
  const options = optionsText
    .split(',')
    .map((option) => option.trim())
    .filter(Boolean)

  const reset = () => {
    setFieldType('text')
    setLabel('')
    setPlaceholder('')
    setDescription('')
    setIsRequired(true)
    setOptionsText('')
  }

  const handleCreate = () => {
    const key = slugify(label)
    if (!key) return
    if (requiresOptions && options.length === 0) return
    if (isContentOnly && !description.trim()) return

    onCreate({
      key,
      label: label.trim(),
      placeholder: isContentOnly ? undefined : placeholder.trim() || undefined,
      helpText: description.trim() || undefined,
      fieldType,
      isRequired: isContentOnly ? false : isRequired,
      options: requiresOptions ? options : undefined,
    })
    reset()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add New Custom Field" maxWidthClassName="max-w-2xl">
      <p className="-mt-3 font-body text-sm text-text-muted">Select a field type and configure its global options</p>

      <div>
        <p className="mb-2 font-body text-sm font-semibold text-text">Select Field Type</p>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
          {FIELD_TYPE_CATALOG.map((entry) => {
            const isSelected = entry.type === fieldType
            return (
              <button
                key={entry.type}
                type="button"
                onClick={() => setFieldType(entry.type)}
                className={`flex flex-col items-center justify-center gap-2 rounded-xl border px-3 py-4 text-center ${
                  isSelected ? 'border-admin-accent bg-admin-accent/5 text-admin-accent' : 'border-border text-text'
                }`}
              >
                {entry.icon === 'text-glyph' ? (
                  <span className="font-display text-base font-bold">AB</span>
                ) : (
                  <entry.icon className="size-5" />
                )}
                <span className="font-body text-xs font-semibold">{entry.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      <div>
        <p className="mb-2 font-body text-sm font-semibold text-text">Configure Properties</p>
        <div className={`grid grid-cols-1 gap-4 ${isContentOnly ? '' : 'sm:grid-cols-2'}`}>
          <TextField
            label={isContentOnly ? 'Title' : 'Field Label'}
            value={label}
            onChange={setLabel}
            placeholder={isContentOnly ? 'e.g. Terms & Conditions' : 'e.g. Company Name'}
            required
          />
          {!isContentOnly && (
            <TextField label="Placeholder Text" value={placeholder} onChange={setPlaceholder} placeholder="e.g. Enter your company" />
          )}
        </div>
        <div className="mt-4">
          <TextareaField
            label={isContentOnly ? 'Content' : 'Description'}
            value={description}
            onChange={setDescription}
            placeholder={
              isContentOnly
                ? 'The text visitors will see, e.g. your Terms & Conditions body'
                : 'Static text shown to the visitor alongside this field, e.g. the terms & conditions body'
            }
            rows={3}
          />
        </div>
        {requiresOptions && (
          <div className="mt-4">
            <TextField
              label="Options (comma-separated)"
              value={optionsText}
              onChange={setOptionsText}
              placeholder="e.g. Yes, No, Maybe"
              required
            />
          </div>
        )}
        {!isContentOnly && (
          <div className="mt-4 flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <div>
              <p className="font-body text-sm font-semibold text-text">Required Field</p>
              <p className="font-body text-xs text-text-muted">This field must be filled to proceed</p>
            </div>
            <ToggleSwitch checked={isRequired} onChange={setIsRequired} label="" />
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleCreate}
          className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-white"
        >
          + Create Field
        </button>
      </div>
    </Modal>
  )
}
