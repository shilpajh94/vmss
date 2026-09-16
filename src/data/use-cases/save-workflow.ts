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
    const existingRules = (await this.approvalWorkflowRuleRepository.list({ visitorCategoryId })).sort((a, b) => a.stepOrder - b.stepOrder)

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
