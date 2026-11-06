import type { EffectiveFormStep, FormField } from '../../../domain/entities/form-builder-schema'
import type { DynamicFieldFileValue, DynamicFieldValue } from './DynamicField'

function isFileValue(value: DynamicFieldValue): value is DynamicFieldFileValue {
  return typeof value === 'object' && value !== null && !Array.isArray(value) && 'fileRef' in value
}

/** Every `file_upload` field among a flat field list (e.g. Visitor Info's or
 * Vehicle Info's own ungrouped custom fields) — used to know which fields in a
 * `customFieldValues`-shaped map must travel as a multipart file instead of a
 * JSON value (backend's "inline file-upload custom fields" contract,
 * 2026-09-24). Grouped file fields are unaffected — they still go through
 * `extractGroupFieldFiles`/`groupFieldFiles[<fieldId>]`.
 */
export function fileUploadFieldsOf<T extends Pick<FormField, 'key' | 'fieldType'>>(fields: T[]): T[] {
  return fields.filter((field) => field.fieldType === 'file_upload')
}

export function requiredFileUploadFieldsOf<T extends Pick<FormField, 'key' | 'fieldType' | 'isRequired'>>(fields: T[]): T[] {
  return fields.filter((field) => field.fieldType === 'file_upload' && field.isRequired)
}

/** Every admin-authored (non-system), ungrouped field across every step
 * except Visitor Info/Vehicle Info (which have their own per-entity buckets
 * — see `fileUploadFieldsOf` above, applied to
 * `visitorInfoCustomFields`/`vehicleInfoCustomFields`) and Consent Agreement
 * (whose answers flow through `consents`, never `customFields` — see
 * `ConsentStep`). Mirrors VMSS_API's
 * `form_builder/validation.py::custom_fields_for_invitation_scope` exactly —
 * a step's own locked/system fields (e.g. Carried Items' `items`/
 * `item_description`) are excluded, since they travel through their own
 * dedicated wire fields, not this shared bucket.
 */
export function findInvitationFields(steps: EffectiveFormStep[]): FormField[] {
  return steps
    .filter((step) => step.key !== 'visitor_info' && step.key !== 'vehicle_info' && step.key !== 'consent_agreement')
    .flatMap((step) => {
      const groupedFieldKeys = new Set(step.groups.flatMap((group) => group.fieldKeys))
      return step.fields.filter((field) => !field.isSystem && !groupedFieldKeys.has(field.key))
    })
}

/** `findInvitationFields`, narrowed to `file_upload` fields — each must
 * travel as a `customFieldFiles[<fieldId>]` multipart part instead of a JSON
 * value.
 */
export function findInvitationFileUploadFields(steps: EffectiveFormStep[]): FormField[] {
  return findInvitationFields(steps).filter((field) => field.fieldType === 'file_upload')
}

export interface ExtractedSingleCustomFieldFiles {
  sanitizedValues: Record<string, DynamicFieldValue>
  files: Record<string, File>
}

/** Strips every one of `fileUploadFields`' answers out of a single flat
 * `customFieldValues`-shaped map (the invitation itself, or one primary
 * contact) and resolves each to the real `File` via `fileRegistry`. The
 * field's key must be entirely absent from the returned JSON value — the
 * backend rejects it with a 422 if both the JSON value and the multipart
 * part are present. The returned `files` map is keyed by the field's `id`
 * (the wire contract's file part key), while `sanitizedValues` stays keyed
 * by `key` (internal wizard state, unaffected by the wire shape).
 */
export function extractSingleCustomFieldFiles(
  fileUploadFields: Pick<FormField, 'id' | 'key'>[],
  values: Record<string, DynamicFieldValue> | undefined,
  fileRegistry: Map<string, File>,
): ExtractedSingleCustomFieldFiles {
  const sanitizedValues: Record<string, DynamicFieldValue> = { ...values }
  const files: Record<string, File> = {}
  for (const field of fileUploadFields) {
    const value = sanitizedValues[field.key]
    delete sanitizedValues[field.key]
    if (isFileValue(value)) {
      const file = fileRegistry.get(value.fileRef)
      if (file) files[field.id] = file
    }
  }
  return { sanitizedValues, files }
}

export interface ExtractedListCustomFieldFiles {
  sanitizedValuesList: Record<string, DynamicFieldValue>[]
  filesByKey: Record<string, File[]>
}

/** Same as `extractSingleCustomFieldFiles`, but for an ordered list of
 * entities' `customFieldValues` (each additional visitor's, or each
 * vehicle's) — each field becomes one order-matched `File[]` list (keyed by
 * the field's `id`), an entity with no answer for that field simply
 * skipped, the same "list, order-matched to instances" convention
 * `visitorIdProofFiles`/`groupFieldFiles` already use.
 */
export function extractListCustomFieldFiles(
  fileUploadFields: Pick<FormField, 'id' | 'key'>[],
  valuesList: (Record<string, DynamicFieldValue> | undefined)[],
  fileRegistry: Map<string, File>,
): ExtractedListCustomFieldFiles {
  const filesByKey: Record<string, File[]> = {}
  const sanitizedValuesList = valuesList.map((values) => {
    const sanitizedValues: Record<string, DynamicFieldValue> = { ...values }
    for (const field of fileUploadFields) {
      const value = sanitizedValues[field.key]
      delete sanitizedValues[field.key]
      if (isFileValue(value)) {
        const file = fileRegistry.get(value.fileRef)
        if (file) {
          filesByKey[field.id] = filesByKey[field.id] ?? []
          filesByKey[field.id].push(file)
        }
      }
    }
    return sanitizedValues
  })
  return { sanitizedValuesList, filesByKey }
}

/** Whether every entity in `valuesList` has a real file answer for every one
 * of `requiredFileUploadFields` — used to block submit client-side the
 * same way missing ID proof/profile photo already are, since the backend
 * rejects an incomplete set with a 422. */
export function hasMissingRequiredCustomFieldFile(
  requiredFileUploadFields: Pick<FormField, 'key'>[],
  valuesList: (Record<string, DynamicFieldValue> | undefined)[],
): boolean {
  if (requiredFileUploadFields.length === 0) return false
  return valuesList.some((values) => requiredFileUploadFields.some((field) => !isFileValue(values?.[field.key])))
}
