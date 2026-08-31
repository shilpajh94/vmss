import type { ApprovalWorkflowRuleRepository } from '../repositories/approval-workflow-rule-repository'
import type { ApprovalWorkflowRule } from '../../domain/entities/approval-workflow-rule-schema'

export class ListApprovalWorkflowRulesUseCase {
  private readonly approvalWorkflowRuleRepository: ApprovalWorkflowRuleRepository

  constructor(approvalWorkflowRuleRepository: ApprovalWorkflowRuleRepository) {
    this.approvalWorkflowRuleRepository = approvalWorkflowRuleRepository
  }

  async execute(visitorCategoryId?: string): Promise<ApprovalWorkflowRule[]> {
    return this.approvalWorkflowRuleRepository.list(visitorCategoryId)
  }
}
