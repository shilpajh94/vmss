import { useState } from 'react'
import { Modal } from '../../../components/ui/Modal'
import { PendingButton } from '../../../components/ui/PendingButton'
import { TextField } from '../../../components/ui/TextField'
import { FORM_BUILDER_NAME_MAX, formBuilderKeyError } from '../form-builder-key'

interface CreateStepModalProps {
  isOpen: boolean
  onClose: () => void
  /** Resolves to `undefined` on success or the failure message, so the name
   * is only cleared once the step actually exists. */
  onCreate: (name: string) => Promise<string | undefined>
}

export function CreateStepModal({ isOpen, onClose, onCreate }: CreateStepModalProps) {
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState<string | undefined>(undefined)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleCreate = async () => {
    const error = formBuilderKeyError(name, 'Step name')
    setNameError(error)
    if (error) return
    setIsSubmitting(true)
    const failure = await onCreate(name)
    setIsSubmitting(false)
    if (!failure) setName('')
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Registration Step">
      <TextField
        label="Step Name"
        value={name}
        onChange={setName}
        placeholder="e.g. NDA Signing"
        required
        error={nameError}
        maxLength={FORM_BUILDER_NAME_MAX}
      />
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
          Create Step
        </PendingButton>
      </div>
    </Modal>
  )
}
