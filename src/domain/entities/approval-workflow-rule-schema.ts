import z from "zod"

export const ApprovalWorkflowRuleSchema = z.object({
  id: z.string(),
  visitorCategoryId: z.string(),
  stepOrder: z.number(),
  approverRoleId: z.string(),
  isMandatory: z.boolean(),
  escalationMinutes: z.number().nullable(),
  autoApproveMinutes: z.number().nullable(),
  isActive: z.boolean(),
})

export type ApprovalWorkflowRule = z.infer<typeof ApprovalWorkflowRuleSchema>

export type ApprovalWorkflowRuleInput = Omit<ApprovalWorkflowRule, "id" | "isActive">

export const ApprovalWorkflowRuleResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: ApprovalWorkflowRuleSchema,
})

export type ApprovalWorkflowRuleResponse = z.infer<typeof ApprovalWorkflowRuleResponseSchema>

export const ApprovalWorkflowRuleListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(ApprovalWorkflowRuleSchema),
  pagination: z.object({
    page: z.number(),
    pageSize: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
})

export type ApprovalWorkflowRuleListResponse = z.infer<typeof ApprovalWorkflowRuleListResponseSchema>
