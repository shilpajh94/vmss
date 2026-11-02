import { useEffect, useState } from 'react'
import { PendingButton } from '../../../components/ui/PendingButton'
import { Modal } from '../../../components/ui/Modal'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import { WholeNumberField } from '../../../components/ui/WholeNumberField'
import { FLOOR_LIMITS, toFloorNumbers, validateFloorNumbers, type FloorNumberDrafts, type FloorNumberErrors } from '../../admin-floors/floor-form-validation'
import type { Floor } from '../../../../domain/entities/floor-schema'
import type { FloorDetailsInput } from '../hooks/use-admin-building-form'

const CAPACITY_TYPE_OPTIONS = [
  { value: 'guests', label: 'Guests' },
  { value: 'staff', label: 'Staff' },
]

const ACCESS_LEVEL_OPTIONS = [
  { value: 'public', label: 'Public' },
  { value: 'restricted', label: 'Restricted' },
  { value: 'secure', label: 'Secure' },
]

type FloorModalValues = Omit<FloorDetailsInput, 'floorNumber' | 'capacity'> & FloorNumberDrafts

const EMPTY_DETAILS: FloorModalValues = {
  name: '',
  floorNumber: 0,
  capacity: 0,
  capacityType: 'guests',
  accessLevel: 'public',
  isActive: true,
}

interface FloorModalProps {
  isOpen: boolean
  initialFloor?: Floor
  isSaving: boolean
  onSave: (details: FloorDetailsInput) => void
  onClose: () => void
}

export function FloorModal({ isOpen, initialFloor, isSaving, onSave, onClose }: FloorModalProps) {
  const [details, setDetails] = useState<FloorModalValues>(EMPTY_DETAILS)
  const [error, setError] = useState<string | undefined>(undefined)
  const [numberErrors, setNumberErrors] = useState<FloorNumberErrors>({})
  const isEditMode = initialFloor !== undefined

  useEffect(() => {
    if (!isOpen) return
    setDetails(initialFloor ? { ...initialFloor } : EMPTY_DETAILS)
    setError(undefined)
    setNumberErrors({})
  }, [isOpen, initialFloor])

  const updateField = <K extends keyof FloorModalValues>(key: K, value: FloorModalValues[K]) => {
    setDetails((current) => ({ ...current, [key]: value }))
  }

  const handleSave = () => {
    const nextNumberErrors = validateFloorNumbers(details)
    const nameError = details.name.trim() ? undefined : 'Floor name is required.'
    setError(nameError)
    setNumberErrors(nextNumberErrors)
    if (nameError || Object.keys(nextNumberErrors).length > 0) return
    onSave({ ...details, ...toFloorNumbers(details) })
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isEditMode ? 'Edit Floor' : 'Add Floor'}>
      <div className="flex flex-col gap-4">
        <TextField
          label="Floor Name"
          required
          value={details.name}
          onChange={(name) => updateField('name', name)}
          error={error}
          maxLength={FLOOR_LIMITS.name}
        />
        <WholeNumberField
          label="Floor Number"
          required
          allowNegative
          value={details.floorNumber}
          onChange={(floorNumber) => updateField('floorNumber', floorNumber)}
          error={numberErrors.floorNumber}
          helperText="0 is the ground floor; basements are negative."
        />
        <div className="flex flex-col gap-4 sm:flex-row">
          <div className="flex-1">
            <WholeNumberField
              label="Capacity"
              value={details.capacity}
              onChange={(capacity) => updateField('capacity', capacity)}
              error={numberErrors.capacity}
            />
          </div>
          <div className="flex-1">
            <SelectField
              label="Unit"
              value={details.capacityType}
              onChange={(capacityType) => updateField('capacityType', capacityType as FloorDetailsInput['capacityType'])}
              options={CAPACITY_TYPE_OPTIONS}
            />
          </div>
        </div>
        <SelectField
          label="Access Level"
          value={details.accessLevel}
          onChange={(accessLevel) => updateField('accessLevel', accessLevel as FloorDetailsInput['accessLevel'])}
          options={ACCESS_LEVEL_OPTIONS}
        />
        <ToggleSwitch
          label={details.isActive ? 'Active' : 'Inactive'}
          checked={details.isActive}
          onChange={(checked) => updateField('isActive', checked)}
        />
      </div>

      <div className="flex items-center justify-end gap-3 pt-2">
        <button type="button" onClick={onClose} className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text">
          Cancel
        </button>
        <PendingButton
          onClick={handleSave}
          pending={isSaving}
          pendingLabel="Saving…"
          className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
        >
          {isEditMode ? 'Save Changes' : 'Add Floor'}
        </PendingButton>
      </div>
    </Modal>
  )
}
