import { useState } from 'react'
import { PlusIcon } from '../../../components/icons'
import type { VisitorInfoFieldState } from '../../visitor-request/hooks/use-visitor-request-wizard'
import type { RegistrationType } from '../../visitor-request/types'
import type { FormField } from '../../../../domain/entities/form-builder-schema'
import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'
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
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
  errors: Record<string, string>
  visitorCategories?: VisitorCategory[]
  /** Branch-configured (form-builder) active/required state for ID proof
   * and profile photo — see `use-visitor-request-wizard.ts`.
   */
  visitorInfoFields: VisitorInfoFieldState
  /** Admin-authored (non-system) Visitor Info fields
   * (add-generic-custom-field-support). */
  customFields: FormField[]
}

export function VisitorInfoStep({
  registrationType,
  onRegistrationTypeChange,
  primaryContact,
  onPrimaryContactChange,
  additionalVisitors,
  onAdditionalVisitorsChange,
  uploadFile,
  getFilePreviewUrl,
  errors,
  visitorCategories,
  visitorInfoFields,
  customFields,
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

      <PrimaryContactCard
        value={primaryContact}
        onChange={onPrimaryContactChange}
        uploadFile={uploadFile}
        getFilePreviewUrl={getFilePreviewUrl}
        errors={errors}
        visitorCategories={visitorCategories}
        visitorInfoFields={visitorInfoFields}
        customFields={customFields}
      />

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
              getFilePreviewUrl={getFilePreviewUrl}
              onAdd={commitVisitor}
              onCancel={cancelAdd}
              visitorInfoFields={visitorInfoFields}
              customFields={customFields}
            />
          )}
        </div>
      )}
    </div>
  )
}
