import { useState } from 'react'
import type { HostEmployee } from '../../../domain/entities/host-employee-schema'
import { Modal } from '../ui/Modal'

interface DelegateInvitationModalProps {
  isOpen: boolean
  isDelegating?: boolean
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
  onConfirm: (delegateUserId: string) => void
  onCancel: () => void
}

export function DelegateInvitationModal({
  isOpen,
  isDelegating,
  approverRoleId,
  stepOrder,
  roleNameById,
  hostEmployees,
  onConfirm,
  onCancel,
}: DelegateInvitationModalProps) {
  const [delegateUserId, setDelegateUserId] = useState('')

  const isOwnershipStep = stepOrder === 0
  // A step configured for a role can only be delegated to someone who holds
  // that role — the picker is locked to the step's own approverRoleId —
  // except the ownership step, which is unfiltered regardless of its
  // approverRoleId (see the prop doc above).
  const stepRoleName = approverRoleId ? roleNameById?.[approverRoleId] : undefined
  const delegateCandidates =
    approverRoleId && !isOwnershipStep
      ? hostEmployees?.filter((employee) => employee.branchRoles.some((branchRole) => branchRole.roleName === stepRoleName))
      : hostEmployees

  const handleCancel = () => {
    setDelegateUserId('')
    onCancel()
  }

  const handleConfirm = () => {
    if (!delegateUserId) return
    onConfirm(delegateUserId)
    setDelegateUserId('')
  }

  return (
    <Modal isOpen={isOpen} onClose={handleCancel} title="Delegate Approval Step">
      <div className="flex flex-col gap-3">
        {approverRoleId && !isOwnershipStep ? (
          <p className="font-body text-[13px] text-text-faint">
            Delegating within role: <span className="font-semibold text-text">{stepRoleName ?? 'the configured role'}</span>
          </p>
        ) : isOwnershipStep ? (
          <p className="font-body text-[13px] text-text-faint">
            Assigning the actual host — any active host employee at this branch can be selected.
          </p>
        ) : null}
        <label className="flex flex-col gap-1.5">
          <span className="font-body text-[13px] font-semibold text-text">Delegate to</span>
          <select
            value={delegateUserId}
            onChange={(event) => setDelegateUserId(event.target.value)}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 font-body text-sm text-text focus:outline-none"
          >
            <option value="">
              {delegateCandidates?.length ? 'Select host…' : approverRoleId && !isOwnershipStep ? `No one currently holds ${stepRoleName}` : 'Select host…'}
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
            disabled={!delegateUserId || isDelegating}
            onClick={handleConfirm}
            className="rounded-full bg-secondary-accent px-4 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-50"
          >
            {isDelegating ? 'Delegating…' : 'Delegate approval'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
