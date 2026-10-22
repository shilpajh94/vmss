import { useState } from 'react'
import type { HostEmployee } from '../../../domain/entities/host-employee-schema'
import { employeeAtBranch, employeeHasRoleAtBranch } from '../../utils/role-name-match'
import { Modal } from '../ui/Modal'
import { confirmSubject } from '../../utils/confirm-subject'
import { FormConfirmStep } from './FormConfirmStep'

interface DelegateInvitationModalProps {
  isOpen: boolean
  visitorName?: string
  trackingId?: string
  isDelegating?: boolean
  // 'approve-and-delegate' is Reception's (stepOrder 0) combined action: the
  // caller has already computed the candidate list from the *next* step's
  // role (see use-invitations-board.ts's `loadNextStepCandidates`) and passes
  // it as `hostEmployees` unfiltered here — this mode never applies the
  // current-step role filter below, which only makes sense in plain 'delegate'
  // mode. Defaults to 'delegate' for every existing call site.
  mode?: 'delegate' | 'approve-and-delegate'
  isLoadingCandidates?: boolean
  approverRoleId?: string | null
  // The invitation's ownership step (`stepOrder` 0, always role-identified
  // for the tenant's default front-office role by default) is exempt from
  // the role-match filter below — the real host is normally not a
  // front-office employee, so restricting the picker to that role would
  // make delegating to the actual host impossible. Every other
  // role-identified step keeps the filter (role-based-invitation-workflow,
  // design.md D3 — mirrors the API's own delegate-eligibility scoping by
  // step position, not by which role the step happens to name).
  stepOrder?: number
  roleNameById?: Record<string, string>
  hostEmployees?: HostEmployee[]
  // The invitation's own branch — the backend enforces that a delegate holds
  // the step's approver role (or, for the ownership step, any role) at this
  // branch specifically (real API error: "Delegate does not hold this step's
  // approver role at the invitation's branch"), so the picker mirrors that.
  branchId?: string | null
  onConfirm: (delegateUserId: string) => void
  onCancel: () => void
}

export function DelegateInvitationModal({
  isOpen,
  visitorName,
  trackingId,
  isDelegating,
  mode = 'delegate',
  isLoadingCandidates,
  approverRoleId,
  stepOrder,
  roleNameById,
  hostEmployees,
  branchId,
  onConfirm,
  onCancel,
}: DelegateInvitationModalProps) {
  const [delegateUserId, setDelegateUserId] = useState('')
  const [isConfirming, setIsConfirming] = useState(false)

  const isApproveAndDelegate = mode === 'approve-and-delegate'
  const isOwnershipStep = stepOrder === 0
  // A step configured for a role can only be delegated to someone who holds
  // that role — the picker is locked to the step's own approverRoleId —
  // except the ownership step, which is unfiltered regardless of its
  // approverRoleId (see the prop doc above). In 'approve-and-delegate' mode
  // the caller already filtered `hostEmployees` to the next step's role, so
  // it is used as-is.
  const stepRoleName = approverRoleId ? roleNameById?.[approverRoleId] : undefined
  // When `approverRoleId` is set but its name can't be resolved (e.g. the
  // admin-scoped `/auth/roles` call 403s for a host/reception-logged-in
  // user — see use-invitations-board.ts), we have no role string left to
  // match branch-role assignments against, so a role-name filter would
  // always come back empty even for a Host who genuinely holds the step's
  // role. Fall back to every active employee at the branch instead — the
  // backend still enforces the real role-at-branch check when the delegate
  // is submitted (see the `branchId` prop doc above).
  const delegateCandidates = isApproveAndDelegate
    ? hostEmployees
    : isOwnershipStep
      ? hostEmployees?.filter((employee) => employeeAtBranch(employee, branchId))
      : approverRoleId
        ? stepRoleName
          ? hostEmployees?.filter((employee) => employeeHasRoleAtBranch(employee, stepRoleName, branchId))
          : hostEmployees?.filter((employee) => employeeAtBranch(employee, branchId))
        : hostEmployees

  const handleCancel = () => {
    if (isDelegating) return
    setDelegateUserId('')
    setIsConfirming(false)
    onCancel()
  }

  const handleConfirm = () => {
    if (!delegateUserId) return
    onConfirm(delegateUserId)
    setDelegateUserId('')
    setIsConfirming(false)
  }

  const delegateName = delegateCandidates?.find((employee) => employee.id === delegateUserId)?.fullName ?? delegateUserId
  const subject = confirmSubject(visitorName, trackingId)

  return (
    <Modal isOpen={isOpen} onClose={handleCancel} title={isApproveAndDelegate ? 'Approve & Delegate' : 'Delegate Approval Step'}>
      {isConfirming ? (
        <FormConfirmStep
          message={
            isApproveAndDelegate
              ? `Approve your step for ${subject} and assign the next step?`
              : `Delegate the current approval step for ${subject}?`
          }
          rows={[{ label: isApproveAndDelegate ? 'Next step approver' : 'Delegate to', value: delegateName }]}
          confirmLabel={isApproveAndDelegate ? 'Approve & delegate' : 'Delegate approval'}
          busyLabel={isApproveAndDelegate ? 'Approving & delegating…' : 'Delegating…'}
          isBusy={isDelegating}
          onBack={() => setIsConfirming(false)}
          onConfirm={handleConfirm}
        />
      ) : (
        <div className="flex flex-col gap-3">
          {isApproveAndDelegate ? (
            <p className="font-body text-[13px] text-text-faint">
              Approves your review and assigns the next step to whoever you pick below.
            </p>
          ) : approverRoleId && !isOwnershipStep ? (
            <p className="font-body text-[13px] text-text-faint">
              {stepRoleName ? (
                <>
                  Delegating within role: <span className="font-semibold text-text">{stepRoleName}</span>
                </>
              ) : (
                "This role's name isn't available to your account — showing all active employees at this branch. The server will still confirm the delegate holds the right role."
              )}
            </p>
          ) : isOwnershipStep ? (
            <p className="font-body text-[13px] text-text-faint">
              Assigning the actual host — any active host employee at this branch can be selected.
            </p>
          ) : null}
          <label className="flex flex-col gap-1.5">
            <span className="font-body text-[13px] font-semibold text-text">{isApproveAndDelegate ? 'Assign next step to' : 'Delegate to'}</span>
            <select
              value={delegateUserId}
              onChange={(event) => setDelegateUserId(event.target.value)}
              disabled={isApproveAndDelegate && isLoadingCandidates}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 font-body text-sm text-text focus:outline-none"
            >
              <option value="">
                {isApproveAndDelegate
                  ? isLoadingCandidates
                    ? 'Loading eligible employees…'
                    : delegateCandidates?.length
                      ? 'Select employee…'
                      : 'No employees are eligible for the next step yet.'
                  : delegateCandidates?.length
                    ? 'Select host…'
                    : stepRoleName
                      ? `No one currently holds ${stepRoleName}`
                      : 'No active employees at this branch'}
              </option>
              {delegateCandidates?.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.fullName}
                </option>
              ))}
            </select>
          </label>

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
              disabled={!delegateUserId || (isApproveAndDelegate && isLoadingCandidates)}
              onClick={() => setIsConfirming(true)}
              className="rounded-full bg-secondary-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
            >
              Review
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
