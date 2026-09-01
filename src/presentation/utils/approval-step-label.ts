import type { CurrentApprovalStep } from '../../domain/entities/invitation-detail-schema'

// Shared by the kanban card badge and the approve/deny toast copy so both
// describe the pending approver the same way.
export function resolveApproverLabel(
  step: CurrentApprovalStep,
  roleNameById: Record<string, string> | undefined,
  employeeNameById: Record<string, string> | undefined,
): string {
  if (step.approverUserId) {
    return employeeNameById?.[step.approverUserId] ?? 'the invitation host'
  }
  return roleNameById?.[step.approverRoleId ?? ''] ?? 'the configured approver role'
}
