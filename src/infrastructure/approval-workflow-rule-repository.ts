import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { ApprovalWorkflowRuleRepository, ListApprovalWorkflowRulesParams } from '../data/repositories/approval-workflow-rule-repository'
import {
  ApprovalWorkflowRuleListResponseSchema,
  ApprovalWorkflowRuleResponseSchema,
  type ApprovalWorkflowRule,
  type ApprovalWorkflowRuleInput,
} from '../domain/entities/approval-workflow-rule-schema'

// Bounded fetch size for the Workflows page's grouped-by-category view - see
// admin-approval-workflows spec's "bounded but not paginated" requirement.
const WORKFLOW_RULES_PAGE_SIZE = 200

export class HttpApprovalWorkflowRuleRepository implements ApprovalWorkflowRuleRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async list(params?: ListApprovalWorkflowRulesParams): Promise<ApprovalWorkflowRule[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_APPROVAL_WORKFLOW_RULES,
      queryParams: {
        visitorCategoryId: params?.visitorCategoryId,
        status: params?.status,
        pageSize: WORKFLOW_RULES_PAGE_SIZE,
      },
      parserSchema: ApprovalWorkflowRuleListResponseSchema,
    })

    return response.data
  }

  async create(input: ApprovalWorkflowRuleInput): Promise<ApprovalWorkflowRule> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_APPROVAL_WORKFLOW_RULE,
      body: input,
      parserSchema: ApprovalWorkflowRuleResponseSchema,
    })

    return response.data
  }

  async update(id: string, input: ApprovalWorkflowRuleInput): Promise<ApprovalWorkflowRule> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_APPROVAL_WORKFLOW_RULE,
      body: input,
      pathParams: { id },
      parserSchema: ApprovalWorkflowRuleResponseSchema,
    })

    return response.data
  }

  async remove(id: string): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_APPROVAL_WORKFLOW_RULE,
      pathParams: { id },
      parserSchema: z.unknown(),
    })
  }
}
