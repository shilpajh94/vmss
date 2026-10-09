import { useState } from 'react'
import { Modal } from '../../../components/ui/Modal'
import { TextField } from '../../../components/ui/TextField'

interface CreateStepModalProps {
  isOpen: boolean
  onClose: () => void
  onCreate: (name: string) => void
}

export function CreateStepModal({ isOpen, onClose, onCreate }: CreateStepModalProps) {
  const [name, setName] = useState('')

  const handleCreate = () => {
    if (!name.trim()) return
    onCreate(name)
    setName('')
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Registration Step">
      <TextField label="Step Name" value={name} onChange={setName} placeholder="e.g. NDA Signing" required />
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
          className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-white"
        >
          Create Step
        </button>
      </div>
    </Modal>
  )
}
