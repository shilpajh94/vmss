import { useEffect, useState } from 'react'
import { Modal } from '../../../components/ui/Modal'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import { DepartmentMultiSelect } from '../../../components/ui/DepartmentMultiSelect'
import type { Floor } from '../../../../domain/entities/building-schema'
import type { Department } from '../../../../domain/entities/department-schema'
import type { FloorDetailsInput } from '../hooks/use-admin-building-form'

const CAPACITY_UNIT_OPTIONS = [
  { value: 'Guests', label: 'Guests' },
  { value: 'Staff', label: 'Staff' },
]

const ACCESS_LEVEL_OPTIONS = [
  { value: 'public', label: 'Public' },
  { value: 'restricted', label: 'Restricted' },
  { value: 'secure', label: 'Secure' },
]

const EMPTY_DETAILS: FloorDetailsInput = {
  name: '',
  capacityCount: 0,
  capacityUnit: 'Guests',
  accessLevel: 'public',
  departmentIds: [],
  status: 'active',
}

interface FloorModalProps {
  isOpen: boolean
  initialFloor?: Floor
  departments: Department[]
  onSave: (details: FloorDetailsInput) => void
  onClose: () => void
}

export function FloorModal({ isOpen, initialFloor, departments, onSave, onClose }: FloorModalProps) {
  const [details, setDetails] = useState<FloorDetailsInput>(EMPTY_DETAILS)
  const [error, setError] = useState<string | undefined>(undefined)
  const isEditMode = initialFloor !== undefined

  useEffect(() => {
    if (!isOpen) return
    setDetails(initialFloor ? { ...initialFloor } : EMPTY_DETAILS)
    setError(undefined)
  }, [isOpen, initialFloor])

  const updateField = <K extends keyof FloorDetailsInput>(key: K, value: FloorDetailsInput[K]) => {
    setDetails((current) => ({ ...current, [key]: value }))
  }

  const handleSave = () => {
    if (!details.name.trim()) {
      setError('Floor name is required.')
      return
    }
    onSave(details)
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isEditMode ? 'Edit Floor' : 'Add Floor'}>
      <div className="flex flex-col gap-4">
        <TextField label="Floor Name" required value={details.name} onChange={(name) => updateField('name', name)} error={error} />
        <div className="flex gap-4">
          <div className="flex-1">
            <TextField
              label="Capacity"
              type="number"
              value={String(details.capacityCount)}
              onChange={(value) => updateField('capacityCount', Number(value) || 0)}
            />
          </div>
          <div className="flex-1">
            <SelectField
              label="Unit"
              value={details.capacityUnit}
              onChange={(capacityUnit) => updateField('capacityUnit', capacityUnit as FloorDetailsInput['capacityUnit'])}
              options={CAPACITY_UNIT_OPTIONS}
            />
          </div>
        </div>
        <SelectField
          label="Access Level"
          value={details.accessLevel}
          onChange={(accessLevel) => updateField('accessLevel', accessLevel as FloorDetailsInput['accessLevel'])}
          options={ACCESS_LEVEL_OPTIONS}
        />
        <DepartmentMultiSelect
          departments={departments}
          selectedIds={details.departmentIds}
          onChange={(departmentIds) => updateField('departmentIds', departmentIds)}
        />
        <ToggleSwitch
          label={details.status === 'active' ? 'Active' : 'Inactive'}
          checked={details.status === 'active'}
          onChange={(checked) => updateField('status', checked ? 'active' : 'inactive')}
        />
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
          {isEditMode ? 'Save Changes' : 'Add Floor'}
        </button>
      </div>
    </Modal>
  )
}
