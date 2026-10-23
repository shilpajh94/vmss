import { useEffect, useState } from 'react'
import { FormSkeleton } from '../ui/Skeleton'
import type { InvitationDetail } from '../../../domain/entities/invitation-detail-schema'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import type { HostEmployee } from '../../../domain/entities/host-employee-schema'
import type { EditInvitationFields } from '../../../data/repositories/visit-request-summary-repository'
import { Modal } from '../ui/Modal'
import { SelectField } from '../ui/SelectField'
import { TextField } from '../ui/TextField'
import { TextareaField } from '../ui/TextareaField'
import { todayAsDateInputValue } from '../../utils/local-date-input-value'
import { useDiscardConfirm } from '../../hooks/use-unsaved-changes-guard'
import { EXPECTED_DURATION_OPTIONS } from '../../utils/expected-duration-options'
import { PURPOSE_OF_VISIT_OPTIONS, purposeLabel } from '../../utils/purpose-of-visit-options'
import { canEditPointOfContact, resolvePointOfContactLabel } from '../../utils/approval-step-label'
import { confirmSubject } from '../../utils/confirm-subject'
import { FormConfirmStep, type ConfirmSummaryRow } from './FormConfirmStep'

interface EditInvitationModalProps {
  isOpen: boolean
  isSaving?: boolean
  detail?: InvitationDetail
  workflowRulesByCategory?: Record<string, ApprovalWorkflowRule[]>
  // Candidates for the Point of Contact dropdown — the selection itself is
  // just another field on `fields`/`EditInvitationFields`, saved together
  // with the rest of the form via the normal "Save changes" flow.
  hostEmployees?: HostEmployee[]
  onConfirm: (fields: EditInvitationFields) => void
  onCancel: () => void
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-overline text-text-faint">{label}</span>
      <span className="truncate font-body text-[13px] font-medium text-text">{value}</span>
    </div>
  )
}

const FIELD_LABELS: Record<keyof EditInvitationFields, string> = {
  purposeOfVisit: 'Purpose of Visit',
  preferredVisitDate: 'Preferred Visit Date',
  preferredVisitTime: 'Preferred Visit Time',
  expectedDuration: 'Expected Duration',
  departmentToVisit: 'Department to Visit',
  additionalNotes: 'Additional Notes',
  pocUserId: 'Point of Contact',
}

function optionLabel(options: { value: string; label: string }[], value: string): string {
  return options.find((option) => option.value === value)?.label ?? value
}

// Only the fields whose value differs from what the invitation already has,
// labelled the way the form shows them — the confirmation step's summary.
function changedFieldRows(initial: EditInvitationFields, fields: EditInvitationFields, hostEmployees: HostEmployee[]): ConfirmSummaryRow[] {
  return (Object.keys(FIELD_LABELS) as (keyof EditInvitationFields)[])
    .filter((key) => (fields[key] ?? '') !== (initial[key] ?? ''))
    .map((key) => {
      const raw = fields[key] ?? ''
      let value = raw
      if (key === 'pocUserId') value = hostEmployees.find((employee) => employee.id === raw)?.fullName ?? raw
      if (key === 'expectedDuration') value = optionLabel(EXPECTED_DURATION_OPTIONS, raw)
      if (key === 'purposeOfVisit') value = optionLabel(PURPOSE_OF_VISIT_OPTIONS, raw)
      return { label: FIELD_LABELS[key], value: value || '—' }
    })
}

function toFormState(detail?: InvitationDetail): EditInvitationFields {
  return {
    purposeOfVisit: purposeLabel(detail?.purposeOfVisit) ?? '',
    preferredVisitDate: detail?.preferredVisitDate ?? '',
    preferredVisitTime: detail?.preferredVisitTime ?? '',
    expectedDuration: detail?.expectedDuration ?? '',
    departmentToVisit: detail?.departmentToVisit ?? '',
    additionalNotes: detail?.additionalNotes ?? '',
    pocUserId: detail?.pocUserId ?? '',
  }
}

// Editable fields mirror exactly what `PATCH /invitations/{id}/edit` accepts
// — purpose, date/time, duration, department, notes, and Point of Contact
// (`pocUserId`, gated by `canEditPointOfContact` — see that helper's doc).
// Deliberately no location/building fields (the API's edit endpoint doesn't
// accept them — there's no backing column to edit) despite earlier planning
// language mentioning them; and no visitor-personal/category/host fields,
// which are rendered read-only below instead (host reassignment stays the
// Delegate action's job).
export function EditInvitationModal({
  isOpen,
  isSaving,
  detail,
  workflowRulesByCategory,
  hostEmployees,
  onConfirm,
  onCancel,
}: EditInvitationModalProps) {
  const [fields, setFields] = useState<EditInvitationFields>(() => toFormState(detail))
  const [isConfirming, setIsConfirming] = useState(false)

  const pointOfContactLabel = detail?.pocName ?? (detail ? resolvePointOfContactLabel(detail, workflowRulesByCategory ?? {}) : undefined)
  const canEditPoc = detail ? canEditPointOfContact(detail, workflowRulesByCategory ?? {}) : false

  // Re-seed local form state whenever a different invitation's modal opens
  // (or its detail arrives after opening) — `RescheduleInvitationModal`/
  // `DelegateInvitationModal` don't need this since they always start blank;
  // Edit needs to start from the invitation's current values instead.
  useEffect(() => {
    if (isOpen) {
      setFields(toFormState(detail))
      setIsConfirming(false)
    }
  }, [isOpen, detail])

  const changedRows = changedFieldRows(toFormState(detail), fields, hostEmployees ?? [])
  const { confirmDiscard } = useDiscardConfirm(isOpen && changedRows.length > 0)

  // Closing asks before dropping edits (D-W6).
  const handleCancel = () => {
    if (isSaving) return
    confirmDiscard(onCancel)
  }

  const handleConfirm = () => {
    onConfirm(fields)
  }

  return (
    <Modal isOpen={isOpen} onClose={handleCancel} title="Edit Invitation" maxWidthClassName="max-w-lg">
      {!detail ? (
        <FormSkeleton bare rows={4} columns={2} label="Loading invitation…" />
      ) : isConfirming ? (
        <FormConfirmStep
          message={`Save these changes to the visit request for ${confirmSubject(detail.primaryContactFullName, detail.trackingId)}?`}
          rows={changedRows}
          confirmLabel="Save changes"
          busyLabel="Saving…"
          isBusy={isSaving}
          onBack={() => setIsConfirming(false)}
          onConfirm={handleConfirm}
        />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-3">
            <h3 className="text-overline text-text-faint">Visitor (read-only)</h3>
            <div className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2 rounded-xl border border-border-subtle p-4">
              <ReadOnlyField label="Name" value={detail.primaryContactFullName} />
              <ReadOnlyField label="Host" value={detail.hostNameOrEmail ?? 'Unassigned — Front Office'} />
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <h3 className="text-overline text-text-faint">Visit details</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <SelectField
                label="Purpose of Visit"
                placeholder="Select purpose"
                options={PURPOSE_OF_VISIT_OPTIONS}
                value={fields.purposeOfVisit ?? ''}
                onChange={(purposeOfVisit) => setFields({ ...fields, purposeOfVisit })}
              />
              {canEditPoc ? (
                <SelectField
                  label="Point of Contact"
                  placeholder="Select point of contact"
                  options={(hostEmployees ?? []).map((employee) => ({ value: employee.id, label: employee.fullName }))}
                  value={fields.pocUserId ?? ''}
                  onChange={(pocUserId) => setFields({ ...fields, pocUserId })}
                />
              ) : (
                <ReadOnlyField label="Point of Contact" value={pointOfContactLabel ?? '—'} />
              )}
              <SelectField
                label="Expected Duration"
                placeholder="Select duration"
                options={EXPECTED_DURATION_OPTIONS}
                value={fields.expectedDuration ?? ''}
                onChange={(expectedDuration) => setFields({ ...fields, expectedDuration })}
              />
              <TextField
                label="Preferred Visit Date"
                type="date"
                min={todayAsDateInputValue()}
                value={fields.preferredVisitDate ?? ''}
                onChange={(preferredVisitDate) => setFields({ ...fields, preferredVisitDate })}
              />
              <TextField
                label="Preferred Visit Time"
                type="time"
                value={fields.preferredVisitTime ?? ''}
                onChange={(preferredVisitTime) => setFields({ ...fields, preferredVisitTime })}
              />
              <TextField
                label="Department to Visit"
                maxLength={255}
                placeholder="Enter department name"
                value={fields.departmentToVisit ?? ''}
                onChange={(departmentToVisit) => setFields({ ...fields, departmentToVisit })}
              />
            </div>
            <TextareaField
              label="Additional Notes / Special Requirements"
              maxLength={2000}
              placeholder="Any special requirements, accessibility needs, or notes for the host…"
              value={fields.additionalNotes ?? ''}
              onChange={(additionalNotes) => setFields({ ...fields, additionalNotes })}
            />
          </div>

          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={handleCancel}
              className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={changedRows.length === 0}
              onClick={() => setIsConfirming(true)}
              className="rounded-full bg-secondary-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
            >
              Review changes
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
