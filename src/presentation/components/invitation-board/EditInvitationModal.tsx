import { useEffect, useState } from 'react'
import type { InvitationDetail } from '../../../domain/entities/invitation-detail-schema'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import type { EffectiveFormStep, FormField } from '../../../domain/entities/form-builder-schema'
import type { HostEmployee } from '../../../domain/entities/host-employee-schema'
import type { EditInvitationFields } from '../../../data/repositories/visit-request-summary-repository'
import { useEffectiveForm } from '../../hooks/use-effective-form'
import { CustomFieldsSection } from '../dynamic-fields/CustomFieldsSection'
import type { DynamicFieldValue } from '../dynamic-fields/DynamicField'
import { findInvitationFields } from '../dynamic-fields/custom-field-files'
import { toFieldAnswers } from '../dynamic-fields/field-answers'
import { Modal } from '../ui/Modal'
import { SelectField } from '../ui/SelectField'
import { TextField } from '../ui/TextField'
import { TextareaField } from '../ui/TextareaField'
import { EXPECTED_DURATION_OPTIONS } from '../../utils/expected-duration-options'
import { PURPOSE_OF_VISIT_OPTIONS } from '../../utils/purpose-of-visit-options'
import { canEditPointOfContact, resolvePointOfContactLabel } from '../../utils/approval-step-label'
import { confirmSubject } from '../../utils/confirm-subject'
import { dateTimeInputToOffsetIso, formatDateTimeInputValue, nowAsDateTimeInputValue, toDateTimeInputValue } from '../../utils/local-datetime-input'
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
  // Needs `invitations:checkout` as well as edit; the board derives it from
  // the same role check as the Check out button. Only matters for visits
  // that are already checked out.
  canEditCheckOutTime?: boolean
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

const FIELD_LABELS: Record<Exclude<keyof EditInvitationFields, 'customFields'>, string> = {
  purposeOfVisit: 'Purpose of Visit',
  preferredVisitDate: 'Preferred Visit Date',
  preferredVisitTime: 'Preferred Visit Time',
  expectedDuration: 'Expected Duration',
  departmentToVisit: 'Department to Visit',
  additionalNotes: 'Additional Notes',
  pocUserId: 'Point of Contact',
  checkedOutAt: 'Check-out Time',
}

function optionLabel(options: { value: string; label: string }[], value: string): string {
  return options.find((option) => option.value === value)?.label ?? value
}

// Only the fields whose value differs from what the invitation already has,
// labelled the way the form shows them — the confirmation step's summary.
function changedFieldRows(
  initial: EditInvitationFields,
  fields: EditInvitationFields,
  hostEmployees: HostEmployee[],
  isCheckedOut: boolean,
): ConfirmSummaryRow[] {
  // A checked-out visit only accepts `checkedOutAt`; every other field is
  // ignored by the backend, so it is the only one compared there.
  return (Object.keys(FIELD_LABELS) as (keyof typeof FIELD_LABELS)[])
    .filter((key) => (key === 'checkedOutAt') === isCheckedOut)
    .filter((key) => (fields[key] ?? '') !== (initial[key] ?? ''))
    .map((key) => {
      const raw = fields[key] ?? ''
      let value = raw
      if (key === 'pocUserId') value = hostEmployees.find((employee) => employee.id === raw)?.fullName ?? raw
      if (key === 'expectedDuration') value = optionLabel(EXPECTED_DURATION_OPTIONS, raw)
      if (key === 'purposeOfVisit') value = optionLabel(PURPOSE_OF_VISIT_OPTIONS, raw)
      if (key === 'checkedOutAt' && raw) value = formatDateTimeInputValue(raw)
      return { label: FIELD_LABELS[key], value: value || '—' }
    })
}


// Invitation-level answers the edit form can change: the admin-authored
// fields of the effective form, plus any system field that already has an
// answer in `customFields` (e.g. Expected Duration, which the wizards now
// submit there instead of the legacy top-level property). File uploads and
// static text have no inline edit control.
function editableCustomFields(detail: InvitationDetail | undefined, steps: EffectiveFormStep[]): FormField[] {
  const answeredIds = new Set((detail?.customFields ?? []).map((answer) => answer.fieldId))
  const authored = new Set(findInvitationFields(steps).map((field) => field.id))
  return steps
    .filter((step) => step.key !== 'visitor_info' && step.key !== 'vehicle_info' && step.key !== 'consent_agreement')
    .flatMap((step) => {
      const grouped = new Set(step.groups.flatMap((group) => group.fieldKeys))
      return step.fields.filter(
        (field) =>
          !grouped.has(field.key) &&
          field.fieldType !== 'file_upload' &&
          field.fieldType !== 'static_text' &&
          (authored.has(field.id) || answeredIds.has(field.id)),
      )
    })
}

function toDynamicValue(raw: unknown): DynamicFieldValue {
  if (typeof raw === 'string' || typeof raw === 'boolean') return raw
  if (Array.isArray(raw) && raw.every((item) => typeof item === 'string')) return raw
  return undefined
}

function toCustomValues(detail: InvitationDetail | undefined, fields: FormField[]): Record<string, DynamicFieldValue> {
  const values: Record<string, DynamicFieldValue> = {}
  for (const field of fields) {
    const answer = detail?.customFields.find((candidate) => candidate.fieldId === field.id)
    const value = toDynamicValue(answer?.value)
    if (value !== undefined) values[field.key] = value
  }
  return values
}

function displayCustomValue(value: DynamicFieldValue): string {
  if (value === undefined || value === '') return ''
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return value.fileName
  return value
}

function changedCustomRows(initial: Record<string, DynamicFieldValue>, current: Record<string, DynamicFieldValue>, fields: FormField[]): ConfirmSummaryRow[] {
  return fields
    .filter((field) => displayCustomValue(initial[field.key]) !== displayCustomValue(current[field.key]))
    .map((field) => ({ label: field.label, value: displayCustomValue(current[field.key]) || '—' }))
}

function toFormState(detail?: InvitationDetail): EditInvitationFields {
  return {
    purposeOfVisit: detail?.purposeOfVisit ?? '',
    preferredVisitDate: detail?.preferredVisitDate ?? '',
    preferredVisitTime: detail?.preferredVisitTime ?? '',
    expectedDuration: detail?.expectedDuration ?? '',
    departmentToVisit: detail?.departmentToVisit ?? '',
    additionalNotes: detail?.additionalNotes ?? '',
    pocUserId: detail?.pocUserId ?? '',
    checkedOutAt: toDateTimeInputValue(detail?.checkedOutAt),
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
  canEditCheckOutTime = false,
  onConfirm,
  onCancel,
}: EditInvitationModalProps) {
  const { steps: formSteps } = useEffectiveForm(detail?.branchId ?? undefined)
  const customFieldDefs = editableCustomFields(detail, formSteps)
  const initialCustomValues = toCustomValues(detail, customFieldDefs)
  const initialCustomKey = JSON.stringify(initialCustomValues)
  const [fields, setFields] = useState<EditInvitationFields>(() => toFormState(detail))
  const [customValues, setCustomValues] = useState<Record<string, DynamicFieldValue>>(initialCustomValues)
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
      setCustomValues(JSON.parse(initialCustomKey))
      setIsConfirming(false)
    }
    // `initialCustomKey` stands in for the derived initial values so the
    // effect re-seeds when the effective form loads, not on every render.
  }, [isOpen, detail, initialCustomKey])

  const isCheckedOut = detail?.status === 'checked_out'
  const hasCustomFields = customFieldDefs.length > 0
  const changedCustom = isCheckedOut ? [] : changedCustomRows(initialCustomValues, customValues, customFieldDefs)
  const changedRows = [
    ...changedFieldRows(toFormState(detail), fields, hostEmployees ?? [], isCheckedOut).filter(
      // With the form's own fields shown, the legacy inputs are hidden.
      (row) => !(hasCustomFields && (row.label === FIELD_LABELS.expectedDuration || row.label === FIELD_LABELS.additionalNotes)),
    ),
    ...changedCustom,
  ]

  const checkedInAtInput = toDateTimeInputValue(detail?.checkedInAt)
  const maxCheckOut = nowAsDateTimeInputValue()
  const checkOutValue = fields.checkedOutAt ?? ''
  let checkOutError: string | undefined
  if (isCheckedOut && checkOutValue) {
    if (checkOutValue > maxCheckOut) checkOutError = 'Check-out time cannot be in the future.'
    else if (checkedInAtInput && checkOutValue < checkedInAtInput) checkOutError = 'Check-out time cannot be before the check-in time.'
  } else if (isCheckedOut) {
    checkOutError = 'Enter a check-out time.'
  }

  const handleCancel = () => {
    if (isSaving) return
    onCancel()
  }

  const handleConfirm = () => {
    if (isCheckedOut) {
      onConfirm({ checkedOutAt: dateTimeInputToOffsetIso(checkOutValue) })
      return
    }
    const { checkedOutAt: _unused, ...rest } = fields
    onConfirm({
      ...rest,
      ...(changedCustom.length > 0 ? { customFields: toFieldAnswers(customValues, customFieldDefs) } : {}),
    })
  }

  return (
    <Modal isOpen={isOpen} onClose={handleCancel} title="Edit Invitation" maxWidthClassName="max-w-lg">
      {!detail ? (
        <div className="flex flex-col items-center gap-2 py-8">
          <div className="size-6 animate-spin rounded-full border-2 border-border-subtle border-t-secondary-accent" />
          <p className="font-body text-sm text-text-muted">Loading invitation…</p>
        </div>
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

          {isCheckedOut ? (
            <div className="flex flex-col gap-3">
              <h3 className="text-overline text-text-faint">Check-out</h3>
              {canEditCheckOutTime ? (
                <TextField
                  label="Check-out Time"
                  type="datetime-local"
                  value={checkOutValue}
                  min={checkedInAtInput || undefined}
                  max={maxCheckOut}
                  error={checkOutError}
                  helperText={
                    detail.checkedOutAutomatically ? 'Checked out automatically by the system — saving a new time marks it as manual.' : undefined
                  }
                  onChange={(checkedOutAt) => setFields({ ...fields, checkedOutAt })}
                />
              ) : (
                <p className="font-body text-sm text-text-muted">
                  This visit is checked out. Only users who can check visitors out may change its check-out time.
                </p>
              )}
            </div>
          ) : (
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
                    options={(hostEmployees ?? []).map((employee) => ({
                      value: employee.id,
                      label: employee.fullName,
                    }))}
                    value={fields.pocUserId ?? ''}
                    onChange={(pocUserId) => setFields({ ...fields, pocUserId })}
                  />
                ) : (
                  <ReadOnlyField label="Point of Contact" value={pointOfContactLabel ?? '—'} />
                )}
                {hasCustomFields ? null : (
                  <SelectField
                    label="Expected Duration"
                    placeholder="Select duration"
                    options={EXPECTED_DURATION_OPTIONS}
                    value={fields.expectedDuration ?? ''}
                    onChange={(expectedDuration) => setFields({ ...fields, expectedDuration })}
                  />
                )}
                <TextField
                  label="Preferred Visit Date"
                  type="date"
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
                  placeholder="Enter department name"
                  value={fields.departmentToVisit ?? ''}
                  onChange={(departmentToVisit) => setFields({ ...fields, departmentToVisit })}
                />
              </div>
              {hasCustomFields ? (
                <CustomFieldsSection fields={customFieldDefs} value={customValues} onChange={setCustomValues} />
              ) : (
                <TextareaField
                  label="Additional Notes / Special Requirements"
                  placeholder="Any special requirements, accessibility needs, or notes for the host…"
                  value={fields.additionalNotes ?? ''}
                  onChange={(additionalNotes) => setFields({ ...fields, additionalNotes })}
                />
              )}
            </div>
          )}

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
              disabled={changedRows.length === 0 || Boolean(checkOutError)}
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
