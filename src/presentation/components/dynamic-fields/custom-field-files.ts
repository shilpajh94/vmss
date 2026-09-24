import type { EffectiveFormStep, FormField } from '../../../domain/entities/form-builder-schema'
import type { DynamicFieldFileValue, DynamicFieldValue } from './DynamicField'

function isFileValue(value: DynamicFieldValue): value is DynamicFieldFileValue {
  return typeof value === 'object' && value !== null && !Array.isArray(value) && 'fileRef' in value
}

/** Every `file_upload` field among a flat field list (e.g. Visitor Info's or
 * Vehicle Info's own ungrouped custom fields) — used to know which keys in a
 * `customFieldValues`-shaped map must travel as a multipart file instead of a
 * JSON value (backend's "inline file-upload custom fields" contract,
 * 2026-09-24). Grouped file fields are unaffected — they still go through
 * `extractGroupFieldFiles`/`groupFieldFiles[<groupKey>]`.
 */
export function fileUploadFieldKeysOf(fields: Pick<FormField, 'key' | 'fieldType'>[]): string[] {
  return fields.filter((field) => field.fieldType === 'file_upload').map((field) => field.key)
}

export function requiredFileUploadFieldKeysOf(fields: Pick<FormField, 'key' | 'fieldType' | 'isRequired'>[]): string[] {
  return fields.filter((field) => field.fieldType === 'file_upload' && field.isRequired).map((field) => field.key)
}

/** Every ungrouped `file_upload` field's key across every step except
 * Visitor Info/Vehicle Info (which have their own per-entity buckets — see
 * `fileUploadFieldKeysOf` above, applied to `visitorInfoCustomFields`/
 * `vehicleInfoCustomFields`) and Consent Agreement (whose answers flow
 * through `consents`, never `customFieldValues`, and never render a file
 * control — see `ConsentStep`). These are the fields whose answer lives in
 * the shared invitation-level `customFieldValues` bucket (Visit Details,
 * Carried Items, any custom step) and must travel as a
 * `customFieldFiles[<key>]` multipart part instead.
 */
export function findInvitationFileUploadFields(steps: EffectiveFormStep[]): FormField[] {
  return steps
    .filter((step) => step.key !== 'visitor_info' && step.key !== 'vehicle_info' && step.key !== 'consent_agreement')
    .flatMap((step) => {
      const groupedFieldKeys = new Set(step.groups.flatMap((group) => group.fieldKeys))
      return step.fields.filter((field) => !groupedFieldKeys.has(field.key) && field.fieldType === 'file_upload')
    })
}

export interface ExtractedSingleCustomFieldFiles {
  sanitizedValues: Record<string, DynamicFieldValue>
  files: Record<string, File>
}

/** Strips every one of `fileUploadFieldKeys`' answers out of a single flat
 * `customFieldValues`-shaped map (the invitation itself, or one primary
 * contact) and resolves each to the real `File` via `fileRegistry`. The
 * field's key must be entirely absent from the returned JSON value — the
 * backend rejects it with a 422 if both the JSON value and the multipart
 * part are present.
 */
export function extractSingleCustomFieldFiles(
  fileUploadFieldKeys: string[],
  values: Record<string, DynamicFieldValue> | undefined,
  fileRegistry: Map<string, File>,
): ExtractedSingleCustomFieldFiles {
  const sanitizedValues: Record<string, DynamicFieldValue> = { ...values }
  const files: Record<string, File> = {}
  for (const key of fileUploadFieldKeys) {
    const value = sanitizedValues[key]
    delete sanitizedValues[key]
    if (isFileValue(value)) {
      const file = fileRegistry.get(value.fileRef)
      if (file) files[key] = file
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
 * vehicle's) — each field key becomes one order-matched `File[]` list, an
 * entity with no answer for that key simply skipped, the same "list,
 * order-matched to instances" convention `visitorIdProofFiles`/
 * `groupFieldFiles` already use.
 */
export function extractListCustomFieldFiles(
  fileUploadFieldKeys: string[],
  valuesList: (Record<string, DynamicFieldValue> | undefined)[],
  fileRegistry: Map<string, File>,
): ExtractedListCustomFieldFiles {
  const filesByKey: Record<string, File[]> = {}
  const sanitizedValuesList = valuesList.map((values) => {
    const sanitizedValues: Record<string, DynamicFieldValue> = { ...values }
    for (const key of fileUploadFieldKeys) {
      const value = sanitizedValues[key]
      delete sanitizedValues[key]
      if (isFileValue(value)) {
        const file = fileRegistry.get(value.fileRef)
        if (file) {
          filesByKey[key] = filesByKey[key] ?? []
          filesByKey[key].push(file)
        }
      }
    }
    return sanitizedValues
  })
  return { sanitizedValuesList, filesByKey }
}

/** Whether every entity in `valuesList` has a real file answer for every one
 * of `requiredFileUploadFieldKeys` — used to block submit client-side the
 * same way missing ID proof/profile photo already are, since the backend
 * rejects an incomplete set with a 422. */
export function hasMissingRequiredCustomFieldFile(
  requiredFileUploadFieldKeys: string[],
  valuesList: (Record<string, DynamicFieldValue> | undefined)[],
): boolean {
  if (requiredFileUploadFieldKeys.length === 0) return false
  return valuesList.some((values) => requiredFileUploadFieldKeys.some((key) => !isFileValue(values?.[key])))
}
