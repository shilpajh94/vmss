import { useState } from 'react'
import type { InvitationDetail, InvitationVehicle } from '../../../domain/entities/invitation-detail-schema'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import type { EffectiveFormStep, FormField } from '../../../domain/entities/form-builder-schema'
import type { FieldAnswer, GroupAnswer } from '../../../domain/entities/form-field-answer-schema'
import { Modal } from '../ui/Modal'
import { CalendarClockIcon, ShieldIcon } from '../icons'
import { formatDateTime } from '../../utils/format-time'
import { resolvePointOfContactLabel } from '../../utils/approval-step-label'
import { prettifyKey } from '../../utils/prettify-key'
import { useEffectiveForm, findFieldById, findGroupById } from '../../hooks/use-effective-form'

interface VisitorInfoModalProps {
  isOpen: boolean
  isLoading?: boolean
  detail?: InvitationDetail
  workflowRulesByCategory?: Record<string, ApprovalWorkflowRule[]>
  // Read-only here — editing Point of Contact happens in EditInvitationModal.
  onClose: () => void
}

const STATUS_TONE_CLASSES: Record<string, string> = {
  submitted: 'bg-info/10 text-info',
  requested: 'bg-info/10 text-info',
  approved: 'bg-success/10 text-success',
  checked_in: 'bg-secondary-accent/10 text-secondary-accent',
  checked_out: 'bg-text-faint/15 text-text-muted',
  denied: 'bg-danger/10 text-danger',
}

function statusToneClass(status: string): string {
  return STATUS_TONE_CLASSES[status] ?? 'bg-neutral-subtle text-text-muted'
}

function statusLabel(status: string): string {
  return status
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function initialsFor(fullName: string): string {
  const parts = fullName.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts[parts.length - 1]?.[0] ?? '')).toUpperCase()
}

function Avatar({
  fullName,
  photoUrl,
  sizeClassName,
  toneClassName,
}: {
  fullName: string
  photoUrl?: string | null
  sizeClassName: string
  toneClassName: string
}) {
  // Photo URLs are short-lived signed links (see use-invitations-board.ts's
  // forced refetch on open) — if one still fails to load (expired, storage
  // hiccup), fall back to the initials badge instead of a broken image icon.
  const [failedToLoad, setFailedToLoad] = useState(false)

  if (photoUrl && !failedToLoad) {
    return (
      <img
        src={photoUrl}
        alt={fullName}
        onError={() => setFailedToLoad(true)}
        className={`shrink-0 rounded-full object-cover ${sizeClassName}`}
      />
    )
  }

  return (
    <span className={`flex shrink-0 items-center justify-center rounded-full font-display font-bold ${sizeClassName} ${toneClassName}`}>
      {initialsFor(fullName)}
    </span>
  )
}

function IdProofField({ label, type, url }: { label: string; type?: string | null; url?: string | null }) {
  if (!type && !url) return null

  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-overline text-text-faint">{label}</span>
      <span className="flex items-center gap-2 font-body text-[13px] font-medium text-text">
        {type ?? '—'}
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="font-body text-[12px] font-semibold text-secondary-accent hover:underline"
          >
            View
          </a>
        ) : null}
      </span>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-overline text-text-faint">{label}</span>
      <span className="truncate font-body text-[13px] font-medium text-text">{value}</span>
    </div>
  )
}

function isFileUrl(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && (value.startsWith('/') || value.startsWith('http'))
}

/** Renders a `file_upload` custom-field answer as "View" link(s). The
 * backend resolves these to signed URLs before returning
 * `GET /invitations/:id` (same as the hardcoded photo/ID-proof fields) —
 * but a submission from before that fix may still carry the raw opaque
 * storage key (e.g. `vmss:<tenant>:...`), so fall back to a plain
 * indicator when a value doesn't look like a URL. */
function FileValueField({ label, value }: { label: string; value: unknown }) {
  const values = Array.isArray(value) ? value : [value]
  const urls = values.filter(isFileUrl)

  if (urls.length === 0) {
    const hasValue = values.some((item) => item !== undefined && item !== null && item !== '')
    return <Field label={label} value={hasValue ? 'File uploaded' : '—'} />
  }

  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-overline text-text-faint">{label}</span>
      <span className="flex flex-wrap items-center gap-2 font-body text-[13px] font-medium text-text">
        {urls.map((url, index) => (
          <a
            key={url}
            href={url}
            target="_blank"
            rel="noreferrer"
            className="font-body text-[12px] font-semibold text-secondary-accent hover:underline"
          >
            {urls.length > 1 ? `View ${index + 1}` : 'View'}
          </a>
        ))}
      </span>
    </div>
  )
}

function SectionLabel({ children }: { children: string }) {
  return <h3 className="text-overline text-text-faint">{children}</h3>
}

/** Read-only formatting for one admin-configured field's raw wire value —
 * `customFields`/`groups` entries come back as plain JSON (`unknown`), not
 * the narrower `DynamicFieldValue` the editable wizards work with, so this
 * can't reuse `formatDynamicFieldValue` as-is. `field` is `undefined` when
 * the fieldId no longer matches any published form-builder field (e.g.
 * removed after this invitation was submitted); the value still renders,
 * just without options-aware prettifying. `file_upload` fields are rendered
 * separately via `FileValueField`, not through this formatter. */
function formatRawFieldValue(value: unknown, field?: FormField): string {
  if (value === undefined || value === null || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) {
    if (value.length === 0) return '—'
    return value.map((item) => (typeof item === 'string' ? prettifyKey(item) : String(item))).join(', ')
  }
  if (typeof value === 'object') {
    const fileName = (value as { fileName?: unknown }).fileName
    return typeof fileName === 'string' ? fileName : JSON.stringify(value)
  }
  const stringValue = String(value)
  return field?.options && field.options.length > 0 ? prettifyKey(stringValue) : stringValue
}

/** Renders a fieldId-addressed custom-field answer list (`customFields` /
 * `primaryContactCustomFields`) as `Field` rows, labeling each answer via
 * the branch's published form-builder config when a match exists and
 * falling back to a prettified fieldId otherwise. Dynamic by construction:
 * it has no fixed list of fields, so it stays correct as admins add/remove
 * custom fields. */
function CustomFieldValueFields({ values, steps }: { values: FieldAnswer[]; steps: EffectiveFormStep[] }) {
  const entries = values.filter(({ value }) => value !== undefined && value !== null && value !== '')
  if (entries.length === 0) return null

  return (
    <>
      {entries.map(({ fieldId, value }) => {
        const field = findFieldById(steps, fieldId)
        const label = field?.label ?? prettifyKey(fieldId)
        if (field?.fieldType === 'file_upload') return <FileValueField key={fieldId} label={label} value={value} />
        return <Field key={fieldId} label={label} value={formatRawFieldValue(value, field)} />
      })}
    </>
  )
}

/** Renders `groups` — one section per non-empty group, each instance as its
 * own card of labeled fields, in the order the backend returned them. */
function GroupFieldValuesSections({ groups, steps }: { groups: GroupAnswer[]; steps: EffectiveFormStep[] }) {
  const groupEntries = groups.filter(({ instances }) => instances.length > 0)

  return (
    <>
      {groupEntries.map(({ groupId, instances }) => {
        const group = findGroupById(steps, groupId)

        return (
          <div key={groupId} className="flex flex-col gap-3">
            <SectionLabel>{`${group?.name ?? prettifyKey(groupId)} (${instances.length})`}</SectionLabel>
            <div className="flex flex-col gap-2">
              {instances.map((instance, index) => (
                <div key={index} className="grid grid-cols-2 gap-x-3 gap-y-1 rounded-xl border border-border-subtle p-3">
                  {instance.map(({ fieldId, value }) => {
                    const field = findFieldById(steps, fieldId)
                    const label = field?.label ?? prettifyKey(fieldId)
                    if (field?.fieldType === 'file_upload') return <FileValueField key={fieldId} label={label} value={value} />
                    return <Field key={fieldId} label={label} value={formatRawFieldValue(value, field)} />
                  })}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </>
  )
}

export function VisitorInfoModal({
  isOpen,
  isLoading,
  detail,
  workflowRulesByCategory,
  onClose,
}: VisitorInfoModalProps) {
  const pointOfContact = detail?.pocName ?? (detail ? resolvePointOfContactLabel(detail, workflowRulesByCategory ?? {}) : undefined)
  // Labels admin-configured custom/group field keys against the branch's
  // published form; an empty/error result just falls back to prettified
  // keys (see `formatRawFieldValue`/`CustomFieldValueFields`) rather than
  // blocking the rest of the modal.
  const { steps: formSteps } = useEffectiveForm(detail?.branchId ?? undefined)

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Visitor Info" maxWidthClassName="max-w-lg">
      {isLoading || !detail ? (
        <div className="flex flex-col items-center gap-2 py-8">
          <div className="size-6 animate-spin rounded-full border-2 border-border-subtle border-t-secondary-accent" />
          <p className="font-body text-sm text-text-muted">Loading visitor info…</p>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex items-start justify-between gap-3 rounded-xl border border-border-subtle bg-bg p-4">
            <div className="flex items-center gap-3">
              <Avatar
                fullName={detail.primaryContactFullName}
                photoUrl={detail.primaryContactPhotoUrl}
                sizeClassName="size-11 text-sm"
                toneClassName="bg-secondary-accent/12 text-secondary-accent"
              />
              <div className="flex flex-col gap-0.5">
                <p className="font-display text-base font-bold text-text">{detail.primaryContactFullName}</p>
                <p className="font-body text-[11px] font-semibold text-text-faint">{detail.trackingId}</p>
              </div>
            </div>
            <span className={`shrink-0 rounded-full px-2.5 py-1 text-caption font-semibold whitespace-nowrap ${statusToneClass(detail.status)}`}>
              {statusLabel(detail.status)}
            </span>
          </div>

          {detail.registrationType === 'group' ? (
            <span className="flex w-fit items-center gap-1.5 rounded-full border border-border-subtle px-2.5 py-1 font-body text-[11px] font-semibold text-text-muted">
              <ShieldIcon className="size-3" />
              Group visit · {1 + detail.visitors.length} visitors
            </span>
          ) : null}

          <div className="flex flex-col gap-3">
            <SectionLabel>Visit details</SectionLabel>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-border-subtle p-4">
              <Field label="Email" value={detail.primaryContactEmail ?? '—'} />
              <Field label="Phone" value={detail.primaryContactPhone ?? '—'} />
              <Field label="Purpose" value={detail.purposeOfVisit} />
              <Field label="Host" value={detail.hostNameOrEmail ?? '—'} />
              <Field label="Point of Contact" value={pointOfContact ?? '—'} />
              <Field label="Department" value={detail.departmentToVisit ?? '—'} />
              {detail.rescheduleCount > 0 ? (
                <>
                  {detail.previousPreferredVisitDate && detail.previousPreferredVisitTime ? (
                    <Field
                      label="Originally scheduled"
                      value={`${detail.previousPreferredVisitDate} ${detail.previousPreferredVisitTime}`}
                    />
                  ) : null}
                  {detail.preferredVisitDate && detail.preferredVisitTime ? (
                    <Field
                      label="Rescheduled to"
                      value={`${detail.preferredVisitDate} ${detail.preferredVisitTime}`}
                    />
                  ) : null}
                  <Field
                    label="Rescheduled"
                    value={`${detail.rescheduleCount}${detail.rescheduleCount > 1 ? ' times' : ' time'}${detail.rescheduledAt ? ` · last ${formatDateTime(detail.rescheduledAt)}` : ''}`}
                  />
                </>
              ) : detail.preferredVisitDate && detail.preferredVisitTime ? (
                <Field label="Scheduled" value={`${detail.preferredVisitDate} ${detail.preferredVisitTime}`} />
              ) : null}
              {detail.carriedItems.length > 0 ? <Field label="Carried items" value={detail.carriedItems.join(', ')} /> : null}
              {detail.carriedItemsDescription ? (
                <div className="col-span-2">
                  <Field label="Carried items description" value={detail.carriedItemsDescription} />
                </div>
              ) : null}
              <IdProofField label="ID proof" type={detail.primaryContactIdProofType} url={detail.primaryContactIdProofUrl} />
              <CustomFieldValueFields values={detail.primaryContactCustomFields} steps={formSteps} />
              {detail.additionalNotes ? (
                <div className="col-span-2">
                  <Field label="Notes" value={detail.additionalNotes} />
                </div>
              ) : null}
            </div>
          </div>

          {detail.customFields.length > 0 ? (
            <div className="flex flex-col gap-3">
              <SectionLabel>Additional details</SectionLabel>
              <div className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-border-subtle p-4">
                <CustomFieldValueFields values={detail.customFields} steps={formSteps} />
              </div>
            </div>
          ) : null}

          {detail.vehicles.length > 0 ? (
            <div className="flex flex-col gap-3">
              <SectionLabel>{`Vehicles (${detail.vehicles.length})`}</SectionLabel>
              <div className="flex flex-col gap-2">
                {detail.vehicles.map((vehicle: InvitationVehicle, index) => (
                  <div key={vehicle.id ?? index} className="grid grid-cols-2 gap-x-3 gap-y-1 rounded-xl border border-border-subtle p-3">
                    <Field label="Type" value={vehicle.vehicleType ?? '—'} />
                    <Field label="License plate" value={vehicle.licensePlate ?? '—'} />
                    <Field label="Make/Model" value={vehicle.makeModel ?? '—'} />
                    <Field label="Color" value={vehicle.color ?? '—'} />
                    <CustomFieldValueFields values={vehicle.customFields} steps={formSteps} />
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <GroupFieldValuesSections groups={detail.groups} steps={formSteps} />

          <div className="flex flex-col gap-3">
            <SectionLabel>Timeline</SectionLabel>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-border-subtle p-4">
              <Field label="Submitted" value={formatDateTime(detail.submittedAt)} />
              <Field label="Expires" value={formatDateTime(detail.expiresAt)} />
              {detail.approvedAt ? <Field label="Approved" value={formatDateTime(detail.approvedAt)} /> : null}
              {detail.checkedInAt ? <Field label="Checked in" value={formatDateTime(detail.checkedInAt)} /> : null}
              {detail.checkedOutAt ? <Field label="Checked out" value={formatDateTime(detail.checkedOutAt)} /> : null}
              {detail.deniedAt ? <Field label="Denied" value={formatDateTime(detail.deniedAt)} /> : null}
              {detail.denialReason ? (
                <div className="col-span-2">
                  <Field label="Denial reason" value={detail.denialReason} />
                </div>
              ) : null}
            </div>
          </div>

          {detail.badgeNumber ? (
            <div className="flex items-center gap-3 rounded-xl border border-border-subtle bg-bg p-4">
              <CalendarClockIcon className="size-4 shrink-0 text-text-faint" />
              <div className="flex flex-1 flex-wrap gap-x-6 gap-y-2">
                <Field label="Badge number" value={detail.badgeNumber} />
                {detail.badgeIssuedAt ? <Field label="Badge issued" value={formatDateTime(detail.badgeIssuedAt)} /> : null}
                {detail.badgeReprintCount > 0 ? <Field label="Badge reprints" value={String(detail.badgeReprintCount)} /> : null}
              </div>
            </div>
          ) : null}

          {detail.watchlistFlagged ? (
            <div className="flex flex-col gap-1 rounded-xl border border-danger/30 bg-danger/8 p-4">
              <span className="font-body text-[13px] font-semibold text-danger">Watchlist flagged</span>
              {detail.watchlistOverrideReason ? (
                <span className="font-body text-[12px] text-danger/80">{detail.watchlistOverrideReason}</span>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
    </Modal>
  )
}
