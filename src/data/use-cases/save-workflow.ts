import type { ApprovalWorkflowRuleRepository } from '../repositories/approval-workflow-rule-repository'

export interface WorkflowLevelInput {
  approverRoleId: string
}

export class SaveWorkflowUseCase {
  private readonly approvalWorkflowRuleRepository: ApprovalWorkflowRuleRepository

  constructor(approvalWorkflowRuleRepository: ApprovalWorkflowRuleRepository) {
    this.approvalWorkflowRuleRepository = approvalWorkflowRuleRepository
  }

  async execute(visitorCategoryId: string, levels: WorkflowLevelInput[]): Promise<void> {
    // Don't trust the backend to have actually scoped `list()` to this
    // category or to have excluded soft-deleted rows (`isActive`) — mirrors
    // the same defensive re-filter `use-invitations-board.ts` and
    // `use-admin-workflow-form.ts` already apply. Without this, a foreign or
    // stale rule can be paired by array index below and have its
    // `visitorCategoryId` silently reassigned to this category via `update()`.
    const existingRules = (await this.approvalWorkflowRuleRepository.list({ visitorCategoryId }))
      .filter((rule) => rule.visitorCategoryId === visitorCategoryId && rule.isActive)
      .sort((a, b) => a.stepOrder - b.stepOrder)

    const operations: Promise<unknown>[] = []
    const maxLength = Math.max(existingRules.length, levels.length)

    for (let index = 0; index < maxLength; index += 1) {
      const level = levels[index]
      const existingRule = existingRules[index]
      const stepOrder = index + 1

      if (level && existingRule) {
        if (existingRule.approverRoleId !== level.approverRoleId || existingRule.stepOrder !== stepOrder) {
          operations.push(
            this.approvalWorkflowRuleRepository.update(existingRule.id, {
              visitorCategoryId,
              stepOrder,
              approverRoleId: level.approverRoleId,
              isMandatory: existingRule.isMandatory,
              escalationMinutes: existingRule.escalationMinutes,
              autoApproveMinutes: existingRule.autoApproveMinutes,
            }),
          )
        }
      } else if (level && !existingRule) {
        operations.push(
          this.approvalWorkflowRuleRepository.create({
            visitorCategoryId,
            stepOrder,
            approverRoleId: level.approverRoleId,
            isMandatory: true,
            escalationMinutes: null,
            autoApproveMinutes: null,
          }),
        )
      } else if (!level && existingRule) {
        operations.push(this.approvalWorkflowRuleRepository.remove(existingRule.id))
      }
    }

    await Promise.all(operations)
  }
}
