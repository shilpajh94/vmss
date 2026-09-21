import { useState } from 'react'
import { SegmentedToggle } from '../../../../components/ui/SegmentedToggle'
import { isValidPhoneNumber } from '../../../../utils/is-valid-phone-number'
import type { FormField } from '../../../../../domain/entities/form-builder-schema'
import type { VisitorInfoFieldState } from '../../hooks/use-visitor-request-wizard'
import {
  createEmptyVisitorFormEntry,
  type RegistrationType,
  type VisitorCategoriesFieldState,
  type VisitorFormEntry,
} from '../../types'
import { VisitorFieldsForm } from './VisitorFieldsForm'

interface VisitorInfoStepProps {
  registrationType: RegistrationType
  onRegistrationTypeChange: (type: RegistrationType) => void
  primaryContact: VisitorFormEntry
  onPrimaryContactChange: (entry: VisitorFormEntry) => void
  /** Locks the primary contact's "Full Name" field — see
   * VisitorFieldsForm's matching prop. Never applies to additional
   * visitors below. */
  primaryContactNameLocked?: boolean
  additionalVisitors: VisitorFormEntry[]
  onAdditionalVisitorsChange: (visitors: VisitorFormEntry[]) => void
  uploadFile: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
  errors: Record<string, string>
  visitorCategoriesState: VisitorCategoriesFieldState
  onRetryVisitorCategories: () => void
  /** Branch-configured (form-builder) active/required state for ID proof
   * and profile photo — see `use-visitor-request-wizard.ts`.
   */
  visitorInfoFields: VisitorInfoFieldState
  /** Admin-authored (non-system) Visitor Info fields, passed straight
   * through to each visitor's own `VisitorFieldsForm`
   * (add-generic-custom-field-support). */
  customFields: FormField[]
}

export function VisitorInfoStep({
  registrationType,
  onRegistrationTypeChange,
  primaryContact,
  onPrimaryContactChange,
  primaryContactNameLocked,
  additionalVisitors,
  onAdditionalVisitorsChange,
  uploadFile,
  getFilePreviewUrl,
  errors,
  visitorCategoriesState,
  onRetryVisitorCategories,
  visitorInfoFields,
  customFields,
}: VisitorInfoStepProps) {
  const [draftVisitor, setDraftVisitor] = useState<VisitorFormEntry | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [draftErrors, setDraftErrors] = useState<Record<string, string>>({})

  const startAddVisitor = () => {
    setEditingIndex(null)
    setDraftErrors({})
    setDraftVisitor(createEmptyVisitorFormEntry())
  }

  const startEditVisitor = (index: number) => {
    setEditingIndex(index)
    setDraftErrors({})
    setDraftVisitor(additionalVisitors[index])
  }

  const cancelDraft = () => {
    setDraftVisitor(null)
    setEditingIndex(null)
    setDraftErrors({})
  }

  const commitDraft = () => {
    if (!draftVisitor) return
    const errors: Record<string, string> = {}
    if (!draftVisitor.fullName) errors.fullName = 'Full name is required.'
    if (!draftVisitor.email && !draftVisitor.phone) errors.email = 'Either email or phone is required.'
    if (draftVisitor.phone && !isValidPhoneNumber(draftVisitor.phone)) errors.phone = 'Enter a valid phone number.'
    if (visitorInfoFields.idProofActive && visitorInfoFields.idProofRequired) {
      if (!draftVisitor.idProofType) errors.idProofType = 'ID proof type is required.'
      if (!draftVisitor.idProofFileRef) errors.idProofFileRef = 'ID proof file is required.'
    }
    if (Object.keys(errors).length > 0) {
      setDraftErrors(errors)
      return
    }
    if (editingIndex === null) {
      onAdditionalVisitorsChange([...additionalVisitors, draftVisitor])
    } else {
      onAdditionalVisitorsChange(additionalVisitors.map((visitor, index) => (index === editingIndex ? draftVisitor : visitor)))
    }
    setDraftVisitor(null)
    setEditingIndex(null)
    setDraftErrors({})
  }

  const removeVisitor = (index: number) => {
    onAdditionalVisitorsChange(additionalVisitors.filter((_, visitorIndex) => visitorIndex !== index))
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <span className="text-body font-medium text-text">Registration Type</span>
        <div className="w-[320px]">
          <SegmentedToggle
            options={[
              { value: 'individual', label: 'Individual' },
              { value: 'group', label: 'Group' },
            ]}
            value={registrationType}
            onChange={(value) => onRegistrationTypeChange(value as RegistrationType)}
            variant="pill"
          />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {registrationType === 'group' && <h3 className="text-h3 text-text">Primary Contact Details</h3>}
        <VisitorFieldsForm
          value={primaryContact}
          onChange={onPrimaryContactChange}
          showContactMethod
          uploadFile={uploadFile}
          getFilePreviewUrl={getFilePreviewUrl}
          errors={errors}
          fullNameLocked={primaryContactNameLocked}
          visitorCategoriesState={visitorCategoriesState}
          onRetryVisitorCategories={onRetryVisitorCategories}
          visitorInfoFields={visitorInfoFields}
          customFields={customFields}
        />
      </div>

      {registrationType === 'group' && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h3 className="text-h3 text-text">Visitor Details</h3>
            <button
              type="button"
              onClick={startAddVisitor}
              className="rounded-lg bg-secondary-accent px-4 py-2 text-body font-semibold text-white"
            >
              + Add Visitor
            </button>
          </div>

          {errors.additionalVisitors && <p className="text-caption text-danger">{errors.additionalVisitors}</p>}

          {additionalVisitors.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-left text-body">
                <thead className="bg-surface text-caption text-text-muted">
                  <tr>
                    <th className="px-4 py-2">#</th>
                    <th className="px-4 py-2">Full Name</th>
                    <th className="px-4 py-2">Email / Phone</th>
                    <th className="px-4 py-2">ID Proof</th>
                    <th className="px-4 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {additionalVisitors.map((visitor, index) => (
                    <tr key={index} className="border-t border-border-subtle text-text">
                      <td className="px-4 py-2">{index + 1}</td>
                      <td className="px-4 py-2">{visitor.fullName}</td>
                      <td className="px-4 py-2">{visitor.email || visitor.phone}</td>
                      <td className="px-4 py-2">{visitor.idProofType}</td>
                      <td className="px-4 py-2">
                        <button type="button" onClick={() => startEditVisitor(index)} className="mr-2 text-secondary-accent">
                          Edit
                        </button>
                        <button type="button" onClick={() => removeVisitor(index)} className="text-danger">
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {draftVisitor && (
            <div className="flex flex-col gap-4 rounded-lg border border-border-subtle bg-surface p-4">
              <h4 className="text-body font-semibold text-text">Add New Visitor</h4>
              <VisitorFieldsForm
                value={draftVisitor}
                onChange={setDraftVisitor}
                showContactMethod={false}
                showExtendedFields={false}
                uploadFile={uploadFile}
                getFilePreviewUrl={getFilePreviewUrl}
                errors={draftErrors}
                visitorInfoFields={visitorInfoFields}
                visitorCategoriesState={visitorCategoriesState}
                onRetryVisitorCategories={onRetryVisitorCategories}
                customFields={customFields}
              />
              <div className="flex gap-3">
                <button type="button" onClick={commitDraft} className="rounded-lg bg-secondary-accent px-4 py-2 text-body font-semibold text-white">
                  Add to List
                </button>
                <button type="button" onClick={cancelDraft} className="text-body font-semibold text-text-muted">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
