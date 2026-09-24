import { useId } from 'react'
import { Checkbox } from '../ui/Checkbox'
import { ExpandableText } from '../ui/ExpandableText'
import { FileUploadField } from '../ui/FileUploadField'
import { SelectField } from '../ui/SelectField'
import { TextField } from '../ui/TextField'
import { TextareaField } from '../ui/TextareaField'
import { prettifyKey } from '../../utils/prettify-key'
import type { FormField, FormFieldType } from '../../../domain/entities/form-builder-schema'

// A file_upload field's answer: an opaque backend ref (from `uploadFile`)
// paired with the original filename for display — mirrors the
// `<x>FileRef`/`<x>FileName` pair `VisitorFieldsForm`'s bespoke ID
// proof/profile image uploads already use, just nested under one key
// instead of two, since a generic field only has one.
export interface DynamicFieldFileValue {
  fileRef: string
  fileName: string
}

export type DynamicFieldValue = string | boolean | string[] | DynamicFieldFileValue | undefined

interface DynamicFieldProps {
  field: FormField
  value: DynamicFieldValue
  onChange: (value: DynamicFieldValue) => void
  /** Required to render an active `file_upload` field's control — without
   * it, such a field falls back to the generic "not supported" message
   * below, same as before this type was wired up. */
  uploadFile?: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
}

const TEXT_LIKE_INPUT_TYPES: Partial<Record<FormFieldType, string>> = {
  text: 'text',
  email: 'email',
  phone: 'tel',
  number: 'number',
  date_picker: 'date',
  time_picker: 'time',
}

// Form Builder doesn't (yet) let an admin configure a file field's accepted
// mime types, unlike the bespoke ID proof/profile image uploads which each
// have their own hardcoded list — this is the same PNG/JPG/PDF allowance as
// ID proof, the more permissive of the two.
const FILE_UPLOAD_ALLOWED_TYPES = ['image/png', 'image/jpeg', 'application/pdf']

function renderControl({ field, value, onChange, uploadFile, getFilePreviewUrl }: DynamicFieldProps, radioGroupName: string) {
  if (field.fieldType === 'file_upload' && uploadFile) {
    const fileValue = value && typeof value === 'object' && !Array.isArray(value) ? value : undefined
    return (
      <FileUploadField
        label={field.label}
        allowedTypes={FILE_UPLOAD_ALLOWED_TYPES}
        helperText="PNG, JPG or PDF (max 5MB)"
        fileName={fileValue?.fileName}
        previewUrl={getFilePreviewUrl?.(fileValue?.fileRef)}
        onUpload={uploadFile}
        onFileRefChange={(fileRef, fileName) => onChange(fileRef && fileName ? { fileRef, fileName } : undefined)}
        required={field.isRequired}
        labelClassName={field.hideLabel ? 'sr-only' : undefined}
      />
    )
  }

  if (field.fieldType === 'static_text') {
    // Display-only content block: no input control, collects no answer.
    // `field.label` is an admin-facing title only (shown as "Title" in the
    // Form Builder), not visitor-facing copy — rendering it as a heading
    // here produced a redundant/mismatched double heading whenever an
    // admin's `helpText` (the actual visitor-facing "Content") already
    // opens with its own title line, which is the common case. Render only
    // `helpText`, in body weight rather than the wrapper's usual muted
    // caption styling, since for this field type it IS the content, not a
    // secondary hint under some other control.
    return <p className="whitespace-pre-wrap text-body text-text">{field.helpText}</p>
  }

  if (field.fieldType === 'checkbox_single' || (field.fieldType === 'toggle_switch' && (!field.options || field.options.length === 0))) {
    // A plain accept/decline toggle with no option set — e.g. a consent
    // statement — rendered as a checkbox to match the mockup. `checkbox_single`
    // is the same boolean/no-options shape, so it shares this branch.
    return (
      <Checkbox checked={Boolean(value)} onChange={(checked) => onChange(checked)} hideLabel={field.hideLabel}>
        {field.label}
      </Checkbox>
    )
  }

  if (field.fieldType === 'checkbox_list' || (field.fieldType === 'toggle_switch' && field.options)) {
    const options = field.options ?? []
    const selected = Array.isArray(value) ? value : []
    return (
      <div className="flex flex-col gap-2">
        <p className={field.hideLabel ? 'sr-only' : 'text-body font-medium text-text'}>{field.label}</p>
        {options.map((option) => (
          <div key={option} className="rounded-lg border border-border px-4 py-3">
            <Checkbox
              checked={selected.includes(option)}
              onChange={(checked) =>
                onChange(checked ? [...selected, option] : selected.filter((item) => item !== option))
              }
            >
              {prettifyKey(option)}
            </Checkbox>
          </div>
        ))}
      </div>
    )
  }

  if (field.fieldType === 'dropdown_select') {
    return (
      <SelectField
        label={field.label}
        value={typeof value === 'string' ? value : ''}
        onChange={onChange}
        required={field.isRequired}
        placeholder={field.placeholder ?? 'Select'}
        options={(field.options ?? []).map((option) => ({ value: option, label: prettifyKey(option) }))}
        labelClassName={field.hideLabel ? 'sr-only' : undefined}
      />
    )
  }

  if (field.fieldType === 'radio_button') {
    const options = field.options ?? []
    return (
      <div className="flex flex-col gap-2">
        <p className={field.hideLabel ? 'sr-only' : 'text-body font-medium text-text'}>{field.label}</p>
        {options.map((option) => (
          <label key={option} className="flex items-center gap-2 rounded-lg border border-border px-4 py-3 text-body text-text">
            <input
              type="radio"
              name={radioGroupName}
              checked={value === option}
              onChange={() => onChange(option)}
              className="size-4 border-border text-primary focus:outline-none focus:ring-2 focus:ring-secondary-accent"
            />
            {prettifyKey(option)}
          </label>
        ))}
      </div>
    )
  }

  if (field.fieldType === 'textarea') {
    return (
      <TextareaField
        label={field.label}
        value={typeof value === 'string' ? value : ''}
        onChange={onChange}
        placeholder={field.placeholder ?? undefined}
        labelClassName={field.hideLabel ? 'sr-only' : undefined}
      />
    )
  }

  const inputType = TEXT_LIKE_INPUT_TYPES[field.fieldType]
  if (inputType) {
    return (
      <TextField
        label={field.label}
        type={inputType}
        value={typeof value === 'string' ? value : ''}
        onChange={onChange}
        placeholder={field.placeholder ?? undefined}
        required={field.isRequired}
        labelClassName={field.hideLabel ? 'sr-only' : undefined}
      />
    )
  }

  return (
    <p className="text-caption text-text-muted">
      &ldquo;{field.label}&rdquo; ({field.fieldType}) isn&apos;t supported inline yet.
    </p>
  )
}

/** Renders one form-builder field for the visitor-facing wizard, given its
 * current value and an onChange callback — the shared primitive behind
 * `ConsentStep`/`CarriedItemsStep`'s dynamic rendering (`form-builder`).
 * Covers every currently-supported field type plus `file_upload` (when the
 * caller threads through `uploadFile`); an unrecognized `fieldType` falls
 * back to a generic "isn't supported inline yet" message rather than
 * throwing, so a future catalog change degrades gracefully here too.
 *
 * `field.helpText` (an admin-authored description, e.g. a hint under an
 * input) renders in full beneath the control for every branch above —
 * wired here once rather than inside each branch, so no field type can
 * forget it. `static_text` is the one exception: its own branch already
 * renders `helpText` as its main content (see that branch's comment), so
 * showing it again here would duplicate it.
 *
 * `radio_button`'s native `name` grouping is scoped to this component
 * instance via `useId()` — a repeatable field group renders the same
 * `field.id` once per instance/row, and a shared literal `name` across rows
 * would make the browser treat every row's radios as one group.
 */
export function DynamicField(props: DynamicFieldProps) {
  const radioGroupName = useId()
  return (
    <div className="flex flex-col gap-2">
      {renderControl(props, radioGroupName)}
      {props.field.fieldType !== 'static_text' && <ExpandableText text={props.field.helpText} />}
    </div>
  )
}
