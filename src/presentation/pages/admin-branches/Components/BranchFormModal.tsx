import { useEffect, useState } from 'react'
import { useDiscardConfirm } from '../../../hooks/use-unsaved-changes-guard'
import { useUnsavedChanges } from '../../../hooks/use-unsaved-changes'
import { PendingButton } from '../../../components/ui/PendingButton'
import { Modal } from '../../../components/ui/Modal'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { TextareaField } from '../../../components/ui/TextareaField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import { COUNTRY_OPTIONS, OPERATING_HOURS_OPTIONS } from '../branch-form-options'
import type { Branch } from '../../../../domain/entities/branch-schema'
import { BRANCH_LIMITS, validateBranchValues, type BranchFormErrors, type BranchFormValues } from '../branch-form-validation'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'
import type { BranchFormState } from '../hooks/use-admin-branches'

const EMPTY_VALUES: BranchFormValues = {
  name: '',
  city: '',
  code: '',
  country: '',
  address: '',
  contactPersonUserId: '',
  contactEmail: '',
  contactPhone: '',
  operatingHoursFrom: undefined,
  operatingHoursTo: undefined,
  notes: undefined,
  isActive: true,
}

interface BranchFormModalProps {
  formState: BranchFormState
  employees: HostEmployee[]
  isSaving: boolean
  onSubmit: (input: Omit<Branch, 'id'>) => void
  onClose: () => void
}

export function BranchFormModal({ formState, employees, isSaving, onSubmit, onClose }: BranchFormModalProps) {
  const [values, setValues] = useState<BranchFormValues>(EMPTY_VALUES)
  const [errors, setErrors] = useState<BranchFormErrors>({})
  const employeeOptions = employees.map((employee) => ({ value: employee.id, label: employee.fullName }))
  const isDirty = useUnsavedChanges(formState ? { ...formState.branch } : EMPTY_VALUES, values) && formState !== undefined
  const { confirmDiscard } = useDiscardConfirm(isDirty)
  // Closing (backdrop, Escape, Cancel) asks before dropping edits.
  const handleClose = () => {
    if (isSaving) return
    confirmDiscard(onClose)
  }

  useEffect(() => {
    if (!formState) return
    setValues({ ...formState.branch })
    setErrors({})
  }, [formState])

  const updateField = <K extends keyof BranchFormValues>(key: K, value: BranchFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }))
  }

  const handleSubmit = () => {
    const nextErrors = validateBranchValues(values)
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      return
    }
    setErrors({})

    onSubmit(values)
  }

  return (
    <Modal isOpen={formState !== undefined} onClose={handleClose} title="Edit Branch">
      <div className="flex flex-col gap-4">
        <TextField
          label="Branch Name"
          value={values.name}
          onChange={(name) => updateField('name', name)}
          error={errors.name}
          required
          maxLength={BRANCH_LIMITS.name}
        />
        <TextField
          label="Branch Code"
          value={values.code}
          onChange={(code) => updateField('code', code)}
          error={errors.code}
          required
          readOnly
        />
        <TextField
          label="Location / City"
          value={values.city}
          onChange={(city) => updateField('city', city)}
          error={errors.city}
          maxLength={BRANCH_LIMITS.city}
          required
        />
        <SelectField
          label="Country"
          value={values.country}
          onChange={(country) => updateField('country', country)}
          options={COUNTRY_OPTIONS}
          error={errors.country}
          required
        />
        <TextareaField
          label="Physical Address"
          required
          value={values.address}
          onChange={(address) => updateField('address', address)}
          rows={2}
          error={errors.address}
          maxLength={BRANCH_LIMITS.address}
        />
        <SelectField
          label="Contact Person"
          value={values.contactPersonUserId}
          onChange={(contactPersonUserId) => updateField('contactPersonUserId', contactPersonUserId)}
          options={employeeOptions}
          placeholder="Select employee..."
          error={errors.contactPersonUserId}
          required
        />
        <TextField
          label="Contact Email Address"
          type="email"
          value={values.contactEmail}
          onChange={(contactEmail) => updateField('contactEmail', contactEmail)}
          error={errors.contactEmail}
          maxLength={BRANCH_LIMITS.contactEmail}
          required
        />
        <TextField
          label="Contact Phone"
          type="tel"
          value={values.contactPhone}
          onChange={(contactPhone) => updateField('contactPhone', contactPhone)}
          error={errors.contactPhone}
          maxLength={BRANCH_LIMITS.contactPhone}
          required
        />
        <div className="flex flex-col gap-4 sm:flex-row">
          <div className="flex-1">
            <SelectField
              label="Operating Hours (From)"
              value={values.operatingHoursFrom ?? ''}
              onChange={(operatingHoursFrom) => updateField('operatingHoursFrom', operatingHoursFrom)}
              options={OPERATING_HOURS_OPTIONS}
            />
          </div>
          <div className="flex-1">
            <SelectField
              label="Operating Hours (To)"
              value={values.operatingHoursTo ?? ''}
              onChange={(operatingHoursTo) => updateField('operatingHoursTo', operatingHoursTo)}
              options={OPERATING_HOURS_OPTIONS}
            />
          </div>
        </div>
        <TextareaField
          label="Internal Administration Notes / Directives"
          value={values.notes ?? ''}
          onChange={(notes) => updateField('notes', notes)}
          rows={2}
          maxLength={BRANCH_LIMITS.notes}
        />
        <ToggleSwitch label="Active" checked={values.isActive} onChange={(checked) => updateField('isActive', checked)} />
      </div>

      <div className="flex items-center justify-end gap-3 pt-2">
        <button type="button" onClick={handleClose} className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text">
          Cancel
        </button>
        <PendingButton
          onClick={handleSubmit}
          pending={isSaving}
          pendingLabel="Saving…"
          className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
        >
          Save Changes
        </PendingButton>
      </div>
    </Modal>
  )
}
