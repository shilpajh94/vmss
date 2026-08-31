import type { ApprovalWorkflowRule, ApprovalWorkflowRuleInput } from '../../domain/entities/approval-workflow-rule-schema'

export interface ApprovalWorkflowRuleRepository {
  list(visitorCategoryId?: string): Promise<ApprovalWorkflowRule[]>
  create(input: ApprovalWorkflowRuleInput): Promise<ApprovalWorkflowRule>
  update(id: string, input: ApprovalWorkflowRuleInput): Promise<ApprovalWorkflowRule>
  remove(id: string): Promise<void>
}
