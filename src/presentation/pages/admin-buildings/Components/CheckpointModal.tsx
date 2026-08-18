import { useEffect, useState } from 'react'
import { Modal } from '../../../components/ui/Modal'
import { TextField } from '../../../components/ui/TextField'

interface CheckpointModalProps {
  isOpen: boolean
  initialName?: string
  onSave: (name: string) => void
  onClose: () => void
}

export function CheckpointModal({ isOpen, initialName, onSave, onClose }: CheckpointModalProps) {
  const [name, setName] = useState('')
  const [error, setError] = useState<string | undefined>(undefined)
  const isEditMode = initialName !== undefined

  useEffect(() => {
    if (!isOpen) return
    setName(initialName ?? '')
    setError(undefined)
  }, [isOpen, initialName])

  const handleSave = () => {
    if (!name.trim()) {
      setError('Checkpoint name is required.')
      return
    }
    onSave(name)
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isEditMode ? 'Edit Checkpoint' : 'Add Checkpoint'}>
      <div className="flex flex-col gap-4">
        <TextField label="Checkpoint Name" required value={name} onChange={setName} error={error} />
      </div>

      <div className="flex items-center justify-end gap-3 pt-2">
        <button type="button" onClick={onClose} className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text">
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-white"
        >
          {isEditMode ? 'Save Changes' : 'Add Checkpoint'}
        </button>
      </div>
    </Modal>
  )
}
