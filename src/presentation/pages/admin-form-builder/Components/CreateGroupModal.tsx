import { useState } from 'react'
import { Collapsible } from '../../../components/ui/Collapsible'
import { Modal } from '../../../components/ui/Modal'
import { TextField } from '../../../components/ui/TextField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import { PendingButton } from '../../../components/ui/PendingButton'
import type { FormFieldGroupCreateInput } from '../../../../domain/entities/form-builder-schema'
import { FORM_BUILDER_NAME_MAX, formBuilderKeyError, slugifyKey } from '../form-builder-key'

interface CreateGroupModalProps {
  isOpen: boolean
  onClose: () => void
  /** Resolves to `undefined` on success or the failure message, so the
   * input is only cleared once the group actually exists. */
  onCreate: (input: FormFieldGroupCreateInput) => Promise<string | undefined>
}

/** Creates a new admin-defined field group on the currently-open step
 * (add-repeatable-field-groups) — mirrors `CreateStepModal`'s shape. A new
 * group starts non-repeatable by default; the repeatable toggle and its
 * min/max range can also be set afterward from the group's own card. */
export function CreateGroupModal({ isOpen, onClose, onCreate }: CreateGroupModalProps) {
  const [name, setName] = useState('')
  const [isRepeatable, setIsRepeatable] = useState(false)
  const [minInstances, setMinInstances] = useState('')
  const [maxInstances, setMaxInstances] = useState('')
  const [nameError, setNameError] = useState<string | undefined>(undefined)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const reset = () => {
    setName('')
    setIsRepeatable(false)
    setMinInstances('')
    setMaxInstances('')
    setNameError(undefined)
  }

  const handleCreate = async () => {
    const error = formBuilderKeyError(name, 'Group name')
    setNameError(error)
    if (error) return
    setIsSubmitting(true)
    const failure = await onCreate({
      key: slugifyKey(name),
      name: name.trim(),
      isRepeatable,
      minInstances: isRepeatable && minInstances.trim() ? Number(minInstances) : undefined,
      maxInstances: isRepeatable && maxInstances.trim() ? Number(maxInstances) : undefined,
    })
    setIsSubmitting(false)
    // A failed save keeps what was typed so it can be fixed and retried.
    if (!failure) reset()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Field Group">
      <p className="-mt-3 font-body text-sm text-text-muted">
        Group related fields together — optionally letting visitors add multiple instances (e.g. "Parcels").
      </p>
      <TextField
        label="Group Name"
        value={name}
        onChange={setName}
        placeholder="e.g. Parcels"
        required
        error={nameError}
        maxLength={FORM_BUILDER_NAME_MAX}
      />
      <ToggleSwitch checked={isRepeatable} onChange={setIsRepeatable} label="Repeatable (visitors can add multiple)" />
      {/* -mt-5 cancels the Modal body's gap-5 while closed. */}
      <Collapsible open={isRepeatable} closedClassName="-mt-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField label="Min Instances" value={minInstances} onChange={setMinInstances} type="number" placeholder="No minimum" />
          <TextField label="Max Instances" value={maxInstances} onChange={setMaxInstances} type="number" placeholder="No maximum" />
        </div>
      </Collapsible>
      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
        >
          Cancel
        </button>
        <PendingButton
          onClick={() => void handleCreate()}
          pending={isSubmitting}
          pendingLabel="Creating…"
          className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
        >
          + Create Group
        </PendingButton>
      </div>
    </Modal>
  )
}
