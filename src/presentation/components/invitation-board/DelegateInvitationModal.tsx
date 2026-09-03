import { useState } from 'react'
import type { HostEmployee } from '../../../domain/entities/host-employee-schema'
import { Modal } from '../ui/Modal'

interface DelegateInvitationModalProps {
  isOpen: boolean
  isDelegating?: boolean
  approverRoleId?: string | null
  roleNameById?: Record<string, string>
  hostEmployees?: HostEmployee[]
  onConfirm: (delegateUserId: string) => void
  onCancel: () => void
}

export function DelegateInvitationModal({
  isOpen,
  isDelegating,
  approverRoleId,
  roleNameById,
  hostEmployees,
  onConfirm,
  onCancel,
}: DelegateInvitationModalProps) {
  const [delegateUserId, setDelegateUserId] = useState('')

  // A step configured for a role can only be delegated to someone who holds
  // that role — the picker is locked to the step's own approverRoleId rather
  // than letting staff pick an unrelated role.
  const stepRoleName = approverRoleId ? roleNameById?.[approverRoleId] : undefined
  const delegateCandidates = approverRoleId
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
        {approverRoleId ? (
          <p className="font-body text-[13px] text-text-faint">
            Delegating within role: <span className="font-semibold text-text">{stepRoleName ?? 'the configured role'}</span>
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
              {delegateCandidates?.length ? 'Select host…' : approverRoleId ? `No one currently holds ${stepRoleName}` : 'Select host…'}
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
