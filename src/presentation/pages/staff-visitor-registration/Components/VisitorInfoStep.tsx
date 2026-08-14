import { useState } from 'react'
import { PlusIcon } from '../../../components/icons'
import type { RegistrationType } from '../../visitor-request/types'
import type { StaffVisitorFormEntry } from '../types'
import { AddVisitorForm } from './AddVisitorForm'
import { PrimaryContactCard } from './PrimaryContactCard'
import { RegistrationTypeToggle } from './RegistrationTypeToggle'
import { VisitorDetailsTable } from './VisitorDetailsTable'

interface VisitorInfoStepProps {
  registrationType: RegistrationType
  onRegistrationTypeChange: (type: RegistrationType) => void
  primaryContact: StaffVisitorFormEntry
  onPrimaryContactChange: (entry: StaffVisitorFormEntry) => void
  additionalVisitors: StaffVisitorFormEntry[]
  onAdditionalVisitorsChange: (visitors: StaffVisitorFormEntry[]) => void
  uploadFile: (file: File) => Promise<string>
  errors: Record<string, string>
}

export function VisitorInfoStep({
  registrationType,
  onRegistrationTypeChange,
  primaryContact,
  onPrimaryContactChange,
  additionalVisitors,
  onAdditionalVisitorsChange,
  uploadFile,
  errors,
}: VisitorInfoStepProps) {
  const [isAdding, setIsAdding] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  const startAdd = () => {
    setEditingIndex(null)
    setIsAdding(true)
  }

  const startEdit = (index: number) => {
    setEditingIndex(index)
    setIsAdding(true)
  }

  const cancelAdd = () => {
    setIsAdding(false)
    setEditingIndex(null)
  }

  const commitVisitor = (visitor: StaffVisitorFormEntry) => {
    if (editingIndex === null) {
      onAdditionalVisitorsChange([...additionalVisitors, visitor])
    } else {
      onAdditionalVisitorsChange(additionalVisitors.map((existing, index) => (index === editingIndex ? visitor : existing)))
    }
    setIsAdding(false)
    setEditingIndex(null)
  }

  const removeVisitor = (index: number) => {
    onAdditionalVisitorsChange(additionalVisitors.filter((_, visitorIndex) => visitorIndex !== index))
  }

  return (
    <div className="flex flex-col gap-6">
      <RegistrationTypeToggle value={registrationType} onChange={onRegistrationTypeChange} />

      <PrimaryContactCard value={primaryContact} onChange={onPrimaryContactChange} uploadFile={uploadFile} errors={errors} />

      {registrationType === 'group' && (
        <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-6">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-base font-semibold text-text">Visitor Details</h3>
            <button
              type="button"
              onClick={startAdd}
              className="flex h-8 items-center gap-2 rounded-full bg-secondary-accent py-1 pr-4 pl-3 text-[13px] font-semibold text-white"
            >
              <PlusIcon className="size-3.5" />
              Add Visitor
            </button>
          </div>

          {errors.additionalVisitors && <p className="text-caption text-danger">{errors.additionalVisitors}</p>}

          <VisitorDetailsTable visitors={additionalVisitors} onEdit={startEdit} onRemove={removeVisitor} />

          {isAdding && (
            <AddVisitorForm
              key={editingIndex ?? 'new'}
              initialValue={editingIndex !== null ? additionalVisitors[editingIndex] : undefined}
              uploadFile={uploadFile}
              onAdd={commitVisitor}
              onCancel={cancelAdd}
            />
          )}
        </div>
      )}
    </div>
  )
}
