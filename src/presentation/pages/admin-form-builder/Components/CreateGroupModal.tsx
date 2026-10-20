import { useState } from 'react'
import { Collapsible } from '../../../components/ui/Collapsible'
import { Modal } from '../../../components/ui/Modal'
import { TextField } from '../../../components/ui/TextField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import type { FormFieldGroupCreateInput } from '../../../../domain/entities/form-builder-schema'

interface CreateGroupModalProps {
  isOpen: boolean
  onClose: () => void
  onCreate: (input: FormFieldGroupCreateInput) => void
}

function slugify(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
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

  const reset = () => {
    setName('')
    setIsRepeatable(false)
    setMinInstances('')
    setMaxInstances('')
  }

  const handleCreate = () => {
    const key = slugify(name)
    if (!key) return
    onCreate({
      key,
      name: name.trim(),
      isRepeatable,
      minInstances: isRepeatable && minInstances.trim() ? Number(minInstances) : undefined,
      maxInstances: isRepeatable && maxInstances.trim() ? Number(maxInstances) : undefined,
    })
    reset()
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Field Group">
      <p className="-mt-3 font-body text-sm text-text-muted">
        Group related fields together — optionally letting visitors add multiple instances (e.g. "Parcels").
      </p>
      <TextField label="Group Name" value={name} onChange={setName} placeholder="e.g. Parcels" required />
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
        <button
          type="button"
          onClick={handleCreate}
          className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent"
        >
          + Create Group
        </button>
      </div>
    </Modal>
  )
}
