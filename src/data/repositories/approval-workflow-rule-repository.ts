import type { ApprovalWorkflowRule, ApprovalWorkflowRuleInput } from '../../domain/entities/approval-workflow-rule-schema'

export interface ListApprovalWorkflowRulesParams {
  visitorCategoryId?: string
  status?: 'active' | 'inactive'
}

export interface ApprovalWorkflowRuleRepository {
  /** Bounded, not paginated - see admin-approval-workflows spec on why (grouping by visitor category). */
  list(params?: ListApprovalWorkflowRulesParams): Promise<ApprovalWorkflowRule[]>
  create(input: ApprovalWorkflowRuleInput): Promise<ApprovalWorkflowRule>
  update(id: string, input: ApprovalWorkflowRuleInput): Promise<ApprovalWorkflowRule>
  remove(id: string): Promise<void>
}
