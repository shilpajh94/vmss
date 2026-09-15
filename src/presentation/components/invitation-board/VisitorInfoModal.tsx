import { useState } from 'react'
import type { InvitationDetail } from '../../../domain/entities/invitation-detail-schema'
import type { ApprovalWorkflowRule } from '../../../domain/entities/approval-workflow-rule-schema'
import { Modal } from '../ui/Modal'
import { CalendarClockIcon, ShieldIcon, TagIcon } from '../icons'
import { formatDateTime } from '../../utils/format-time'
import { resolvePointOfContactLabel } from '../../utils/approval-step-label'

interface VisitorInfoModalProps {
  isOpen: boolean
  isLoading?: boolean
  detail?: InvitationDetail
  workflowRulesByCategory?: Record<string, ApprovalWorkflowRule[]>
  // Reassigning the host/point of contact has real backend rules (role and
  // branch eligibility, and Reception's own step can't be delegated directly
  // — see use-invitations-board.ts's `delegate`) that DelegateInvitationModal
  // already encodes correctly, so "Edit" here opens that flow rather than
  // duplicating its logic.
  onEditHost?: () => void
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

function SectionLabel({ children }: { children: string }) {
  return <h3 className="text-overline text-text-faint">{children}</h3>
}

function HostField({
  hostNameOrEmail,
  onEditHost,
}: {
  hostNameOrEmail: string | null
  onEditHost?: () => void
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-overline text-text-faint">Host</span>
      <span className="flex items-center gap-2">
        <span className="truncate font-body text-[13px] font-medium text-text">{hostNameOrEmail ?? '—'}</span>
        {onEditHost ? (
          <button
            type="button"
            onClick={onEditHost}
            className="shrink-0 font-body text-[11px] font-semibold text-secondary-accent hover:underline"
          >
            Edit
          </button>
        ) : null}
      </span>
    </div>
  )
}

export function VisitorInfoModal({
  isOpen,
  isLoading,
  detail,
  workflowRulesByCategory,
  onEditHost,
  onClose,
}: VisitorInfoModalProps) {
  const pointOfContact = detail ? resolvePointOfContactLabel(detail, workflowRulesByCategory ?? {}) : undefined

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
              <Field label="Purpose" value={detail.purposeOfVisit} />
              <HostField hostNameOrEmail={detail.hostNameOrEmail} onEditHost={onEditHost} />
              {pointOfContact ? <Field label="Point of Contact" value={pointOfContact} /> : null}
              <Field label="Department" value={detail.departmentToVisit ?? '—'} />
              <Field label="Expected duration" value={detail.expectedDuration ?? '—'} />
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
              <IdProofField label="ID proof" type={detail.primaryContactIdProofType} url={detail.primaryContactIdProofUrl} />
              {detail.additionalNotes ? (
                <div className="col-span-2">
                  <Field label="Notes" value={detail.additionalNotes} />
                </div>
              ) : null}
            </div>
          </div>

          {detail.visitors.length > 0 ? (
            <div className="flex flex-col gap-3">
              <SectionLabel>{`Group visitors (${detail.visitors.length})`}</SectionLabel>
              <div className="flex flex-col gap-2">
                {detail.visitors.map((visitor) => (
                  <div key={visitor.id} className="flex items-center gap-3 rounded-xl border border-border-subtle p-3">
                    <Avatar
                      fullName={visitor.fullName}
                      photoUrl={visitor.photoUrl}
                      sizeClassName="size-8 text-xs"
                      toneClassName="bg-neutral-subtle text-text"
                    />
                    <div className="grid min-w-0 flex-1 grid-cols-2 gap-x-3 gap-y-0.5">
                      <p className="col-span-2 truncate font-body text-[13px] font-semibold text-text">{visitor.fullName}</p>
                      <p className="truncate font-body text-[11px] text-text-muted">{visitor.email ?? '—'}</p>
                      <p className="truncate font-body text-[11px] text-text-muted">{visitor.phone ?? '—'}</p>
                    </div>
                    {visitor.idProofType ? (
                      <span className="flex shrink-0 items-center gap-1 rounded-full bg-neutral-subtle px-2 py-0.5 font-body text-[10px] font-semibold whitespace-nowrap text-text-muted">
                        <TagIcon className="size-2.5" />
                        {visitor.idProofType}
                      </span>
                    ) : null}
                    {visitor.idProofUrl ? (
                      <a
                        href={visitor.idProofUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="shrink-0 font-body text-[11px] font-semibold whitespace-nowrap text-secondary-accent hover:underline"
                      >
                        View ID
                      </a>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

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
