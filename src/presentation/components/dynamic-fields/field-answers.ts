import type { FormField } from '../../../domain/entities/form-builder-schema'
import type { ConsentAnswer, FieldAnswer } from '../../../domain/entities/form-field-answer-schema'
import type { DynamicFieldValue } from './DynamicField'

/** Converts a flat, key-indexed answer map (internal wizard state) into the
 * wire contract's fieldId-indexed array — only fields with a present answer
 * are included. */
export function toFieldAnswers(
  values: Record<string, DynamicFieldValue> | undefined,
  fields: Pick<FormField, 'id' | 'key'>[],
): FieldAnswer[] {
  if (!values) return []
  return fields.filter((field) => field.key in values).map((field) => ({ fieldId: field.id, value: values[field.key] }))
}

/** Every one of `fields`, not just the ones the visitor touched — the
 * backend requires `consents` to cover every active consent field. */
export function toConsentAnswers(consent: Record<string, boolean>, fields: Pick<FormField, 'id' | 'key'>[]): ConsentAnswer[] {
  return fields.map((field) => ({ fieldId: field.id, accepted: Boolean(consent[field.key]) }))
}
