import { useState } from 'react'
import { CustomFieldsSection } from './CustomFieldsSection'
import type { DynamicFieldValue } from './DynamicField'
import { formatDynamicFieldValue } from './format-dynamic-field-value'
import type { FormField } from '../../../domain/entities/form-builder-schema'

export type GroupInstance = Record<string, DynamicFieldValue>

interface RepeatableFieldGroupProps {
  /** The group's display name, used in headings and the "+ Add" button
   * label (e.g. "Parcels" -> "+ Add Parcels"). */
  groupName: string
  /** This group's own fields, in step order — every instance's answer map
   * is keyed by these fields' `key`s. */
  fields: FormField[]
  minInstances: number | null
  maxInstances: number | null
  instances: GroupInstance[]
  onChange: (instances: GroupInstance[]) => void
  /** Required for an active `file_upload` field among `fields` to render a
   * working upload control instead of falling back to "not supported". */
  uploadFile?: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
  /** Min-instances error set by the wizard's Next validation. */
  error?: string
}

/** Generalizes `VehicleInfoStep`'s add/edit/remove-instance-row UI (a table
 * of committed instances plus a draft form) to work for ANY admin-defined
 * repeatable field group (add-repeatable-field-groups), not just the two
 * built-in "vehicles"/"visitors" cases. Used by `GenericConfiguredStep` for
 * a custom step's own groups; `VehicleInfoStep`/`VisitorInfoStep` keep their
 * existing, bespoke implementations (see their own file comments) rather
 * than being rebased onto this, since each has extra per-entity fields
 * (vehicle type, ID-proof upload) this generic shape doesn't model.
 */
export function RepeatableFieldGroup({
  groupName,
  fields,
  minInstances,
  maxInstances,
  instances,
  onChange,
  uploadFile,
  getFilePreviewUrl,
  error,
}: RepeatableFieldGroupProps) {
  const [draft, setDraft] = useState<GroupInstance | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [draftError, setDraftError] = useState<string | undefined>(undefined)
  const [removeError, setRemoveError] = useState<string | undefined>(undefined)

  const atMax = maxInstances !== null && instances.length >= maxInstances

  const startAdd = () => {
    setEditingIndex(null)
    setDraftError(undefined)
    setDraft({})
  }

  const startEdit = (index: number) => {
    setEditingIndex(index)
    setDraftError(undefined)
    setDraft(instances[index])
  }

  const cancelDraft = () => {
    setDraft(null)
    setEditingIndex(null)
    setDraftError(undefined)
  }

  const commitDraft = () => {
    if (!draft) return
    const missingRequired = fields.some((field) => field.isRequired && !draft[field.key])
    if (missingRequired) {
      setDraftError('Please fill in every required field before adding.')
      return
    }
    if (editingIndex === null) {
      if (atMax) {
        setDraftError(`You can add at most ${maxInstances} ${groupName.toLowerCase()}.`)
        return
      }
      onChange([...instances, draft])
    } else {
      onChange(instances.map((instance, index) => (index === editingIndex ? draft : instance)))
    }
    setDraft(null)
    setEditingIndex(null)
    setDraftError(undefined)
  }

  const removeInstance = (index: number) => {
    if (minInstances !== null && instances.length <= minInstances) {
      setRemoveError(`At least ${minInstances} ${groupName.toLowerCase()} ${minInstances === 1 ? 'is' : 'are'} required.`)
      return
    }
    setRemoveError(undefined)
    onChange(instances.filter((_, instanceIndex) => instanceIndex !== index))
  }

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border-subtle bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-h3 text-text">{groupName}</h3>
          {(minInstances !== null || maxInstances !== null) && (
            <p className="text-caption text-text-muted">
              {minInstances !== null && maxInstances !== null
                ? `Add between ${minInstances} and ${maxInstances}.`
                : minInstances !== null
                  ? `Add at least ${minInstances}.`
                  : `Add up to ${maxInstances}.`}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={startAdd}
          disabled={atMax}
          className="cursor-pointer rounded-lg bg-secondary-accent px-4 py-2 text-body font-semibold text-on-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          + Add {groupName}
        </button>
      </div>

      {error && instances.length < (minInstances ?? 0) && <p className="text-caption text-danger">{error}</p>}
      {removeError && <p className="text-caption text-danger">{removeError}</p>}

      {instances.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-body">
            <thead className="bg-surface-inset text-caption text-text-muted">
              <tr>
                <th className="px-4 py-2">#</th>
                {fields.map((field) => (
                  <th key={field.key} className="px-4 py-2">
                    {field.label}
                  </th>
                ))}
                <th className="sticky right-0 bg-surface-inset px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {instances.map((instance, index) => (
                <tr key={index} className="border-t border-border-subtle text-text">
                  <td className="px-4 py-2">{index + 1}</td>
                  {fields.map((field) => (
                    <td key={field.key} className="px-4 py-2">
                      {formatDynamicFieldValue(field, instance[field.key])}
                    </td>
                  ))}
                  <td className="sticky right-0 bg-surface px-4 py-2 whitespace-nowrap">
                    <button type="button" onClick={() => startEdit(index)} className="mr-2 cursor-pointer text-secondary-accent max-lg:min-h-10 max-lg:px-2">
                      Edit
                    </button>
                    <button type="button" onClick={() => removeInstance(index)} className="cursor-pointer text-danger max-lg:min-h-10 max-lg:px-2">
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {draft && (
        <div className="flex flex-col gap-4 rounded-lg border border-border-subtle bg-surface-inset p-4">
          <h4 className="text-body font-semibold text-text">{editingIndex === null ? `Add ${groupName}` : `Edit ${groupName}`}</h4>
          {fields.length > 0 ? (
            <CustomFieldsSection fields={fields} value={draft} onChange={setDraft} uploadFile={uploadFile} getFilePreviewUrl={getFilePreviewUrl} />
          ) : (
            // No fields configured on this group yet — nothing to render, but
            // instances can still be added/removed as bare rows.
            <p className="text-caption text-text-muted">This group has no fields configured yet.</p>
          )}
          {draftError && <p className="text-caption text-danger">{draftError}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={commitDraft} className="cursor-pointer rounded-lg bg-secondary-accent px-4 py-2 text-body font-semibold text-on-accent">
              {editingIndex === null ? 'Add to List' : 'Save Changes'}
            </button>
            <button type="button" onClick={cancelDraft} className="cursor-pointer text-body font-semibold text-text-muted">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
