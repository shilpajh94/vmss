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

function renderControl({ field, value, onChange, uploadFile, getFilePreviewUrl }: DynamicFieldProps) {
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
      />
    )
  }

  if (field.fieldType === 'static_text') {
    // Display-only content block: no input control, collects no answer.
    // Its body renders via the wrapper's unconditional `ExpandableText`
    // call below, the same mechanism every other field type's description
    // already uses.
    return <p className="text-body font-semibold text-text">{field.label}</p>
  }

  if (field.fieldType === 'toggle_switch' && (!field.options || field.options.length === 0)) {
    // A plain accept/decline toggle with no option set — e.g. a consent
    // statement — rendered as a checkbox to match the mockup.
    return (
      <Checkbox checked={Boolean(value)} onChange={(checked) => onChange(checked)}>
        {field.label}
      </Checkbox>
    )
  }

  if (field.fieldType === 'checkbox_list' || (field.fieldType === 'toggle_switch' && field.options)) {
    const options = field.options ?? []
    const selected = Array.isArray(value) ? value : []
    return (
      <div className="flex flex-col gap-2">
        <p className="text-body font-medium text-text">{field.label}</p>
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
      />
    )
  }

  if (field.fieldType === 'textarea') {
    return (
      <TextareaField
        label={field.label}
        value={typeof value === 'string' ? value : ''}
        onChange={onChange}
        placeholder={field.placeholder ?? undefined}
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
 * Covers every "simple" field type plus `file_upload` (when the caller
 * threads through `uploadFile`); `dynamic_table`/`signature_pad`/
 * `rich_text_block` still aren't wired up for inline rendering (design.md's
 * Non-Goals/known limitations) — no step this serves today uses one, so
 * this is a graceful fallback, not a gap in what's actually exercised.
 *
 * `field.helpText` (an admin-authored description, e.g. a terms-and-
 * conditions body) renders in full beneath the control for every branch
 * above — wired here once rather than inside each branch, so no field type
 * can forget it.
 */
export function DynamicField(props: DynamicFieldProps) {
  return (
    <div className="flex flex-col gap-2">
      {renderControl(props)}
      <ExpandableText text={props.field.helpText} />
    </div>
  )
}
