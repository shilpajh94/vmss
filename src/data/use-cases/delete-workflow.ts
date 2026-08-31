import type { ApprovalWorkflowRuleRepository } from '../repositories/approval-workflow-rule-repository'

export class DeleteWorkflowUseCase {
  private readonly approvalWorkflowRuleRepository: ApprovalWorkflowRuleRepository

  constructor(approvalWorkflowRuleRepository: ApprovalWorkflowRuleRepository) {
    this.approvalWorkflowRuleRepository = approvalWorkflowRuleRepository
  }

  async execute(ruleIds: string[]): Promise<void> {
    await Promise.all(ruleIds.map((ruleId) => this.approvalWorkflowRuleRepository.remove(ruleId)))
  }
}
