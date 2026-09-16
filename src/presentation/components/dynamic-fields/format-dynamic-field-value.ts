import { prettifyKey } from '../../utils/prettify-key'
import type { FormField } from '../../../domain/entities/form-builder-schema'
import type { DynamicFieldValue } from './DynamicField'

const EMPTY_VALUE = '—'

/** Formats one form-builder field's submitted value for read-only display
 * (a vehicle list column, a Review & Confirm summary row) — the display-side
 * counterpart to `DynamicField`'s editable rendering. Shared so the table
 * and the summary never diverge on how a boolean/array value reads. */
export function formatDynamicFieldValue(field: FormField, value: DynamicFieldValue): string {
  if (value === undefined || value === '') return EMPTY_VALUE

  if (typeof value === 'boolean') return value ? 'Yes' : 'No'

  if (Array.isArray(value)) {
    return value.length > 0 ? value.map(prettifyKey).join(', ') : EMPTY_VALUE
  }

  return field.options && field.options.length > 0 ? prettifyKey(value) : value
}
