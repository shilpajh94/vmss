import { Checkbox } from '../ui/Checkbox'
import { ExpandableText } from '../ui/ExpandableText'
import { SelectField } from '../ui/SelectField'
import { TextField } from '../ui/TextField'
import { TextareaField } from '../ui/TextareaField'
import { prettifyKey } from '../../utils/prettify-key'
import type { FormField, FormFieldType } from '../../../domain/entities/form-builder-schema'

export type DynamicFieldValue = string | boolean | string[] | undefined

interface DynamicFieldProps {
  field: FormField
  value: DynamicFieldValue
  onChange: (value: DynamicFieldValue) => void
}

const TEXT_LIKE_INPUT_TYPES: Partial<Record<FormFieldType, string>> = {
  text: 'text',
  email: 'email',
  phone: 'tel',
  number: 'number',
  date_picker: 'date',
  time_picker: 'time',
}

function renderControl({ field, value, onChange }: DynamicFieldProps) {
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
 * Covers every "simple" field type; `file_upload`/`dynamic_table`/
 * `signature_pad`/`rich_text_block` aren't wired up for inline rendering
 * yet (design.md's Non-Goals/known limitations) — neither default step
 * this serves today uses one, so this is a graceful fallback, not a gap in
 * what's actually exercised.
 *
 * `field.helpText` (an admin-authored description, e.g. a terms-and-
 * conditions body) renders beneath the control for every branch above,
 * truncated with a see-more/see-less toggle — wired here once rather than
 * inside each branch, so no field type can forget it.
 */
export function DynamicField(props: DynamicFieldProps) {
  return (
    <div className="flex flex-col gap-2">
      {renderControl(props)}
      <ExpandableText text={props.field.helpText} />
    </div>
  )
}
