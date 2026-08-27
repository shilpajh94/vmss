import { useState } from 'react'
import { SegmentedToggle } from '../../../../components/ui/SegmentedToggle'
import type { VisitorCategory } from '../../../../../domain/entities/visitor-category-schema'
import { createEmptyVisitorFormEntry, type RegistrationType, type VisitorFormEntry } from '../../types'
import { VisitorFieldsForm } from './VisitorFieldsForm'

interface VisitorInfoStepProps {
  registrationType: RegistrationType
  onRegistrationTypeChange: (type: RegistrationType) => void
  primaryContact: VisitorFormEntry
  onPrimaryContactChange: (entry: VisitorFormEntry) => void
  additionalVisitors: VisitorFormEntry[]
  onAdditionalVisitorsChange: (visitors: VisitorFormEntry[]) => void
  uploadFile: (file: File) => Promise<string>
  errors: Record<string, string>
  visitorCategories?: VisitorCategory[]
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
  visitorCategories,
}: VisitorInfoStepProps) {
  const [draftVisitor, setDraftVisitor] = useState<VisitorFormEntry | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  const startAddVisitor = () => {
    setEditingIndex(null)
    setDraftVisitor(createEmptyVisitorFormEntry())
  }

  const startEditVisitor = (index: number) => {
    setEditingIndex(index)
    setDraftVisitor(additionalVisitors[index])
  }

  const cancelDraft = () => {
    setDraftVisitor(null)
    setEditingIndex(null)
  }

  const commitDraft = () => {
    if (!draftVisitor) return
    if (editingIndex === null) {
      onAdditionalVisitorsChange([...additionalVisitors, draftVisitor])
    } else {
      onAdditionalVisitorsChange(additionalVisitors.map((visitor, index) => (index === editingIndex ? draftVisitor : visitor)))
    }
    setDraftVisitor(null)
    setEditingIndex(null)
  }

  const removeVisitor = (index: number) => {
    onAdditionalVisitorsChange(additionalVisitors.filter((_, visitorIndex) => visitorIndex !== index))
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <span className="text-body font-medium text-text">Registration Type</span>
        <SegmentedToggle
          options={[
            { value: 'individual', label: 'Individual' },
            { value: 'group', label: 'Group' },
          ]}
          value={registrationType}
          onChange={(value) => onRegistrationTypeChange(value as RegistrationType)}
        />
      </div>

      <div className="flex flex-col gap-3">
        {registrationType === 'group' && <h3 className="text-h3 text-text">Primary Contact Details</h3>}
        <VisitorFieldsForm
          value={primaryContact}
          onChange={onPrimaryContactChange}
          showContactMethod
          uploadFile={uploadFile}
          errors={errors}
          visitorCategories={visitorCategories}
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
                uploadFile={uploadFile}
                visitorCategories={visitorCategories}
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
