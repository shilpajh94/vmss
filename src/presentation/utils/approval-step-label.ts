import type { CurrentApprovalStep, InvitationDetail } from '../../domain/entities/invitation-detail-schema'
import type { ApprovalWorkflowRule } from '../../domain/entities/approval-workflow-rule-schema'

// `CurrentApprovalStep.stepOrder` is 0-indexed (Reception's own step is
// `stepOrder: 0`) — confirmed 2026-09-14 against the live API across several
// real invitations. `ApprovalWorkflowRule.stepOrder` (the category's
// configured rules) is separately 1-indexed. Used only as a last-resort
// fallback below — see `resolveCurrentLevel`, which prefers matching the
// step's role against the category's *live* rules instead, since the
// invitation-side `stepOrder`/`totalSteps` snapshot itself can be stale (a
// confirmed backend bug: the snapshot can reference an outdated version of
// the category's workflow, taken before an admin's later edit).
export function displayStepLevel(stepOrder: number): number {
  return stepOrder + 1
}

function sortedRulesFor(
  visitorCategoryId: string | null | undefined,
  workflowRulesByCategory: Record<string, ApprovalWorkflowRule[]>,
): ApprovalWorkflowRule[] | undefined {
  const rules = visitorCategoryId ? workflowRulesByCategory[visitorCategoryId] : undefined
  if (!rules || rules.length === 0) return undefined
  return [...rules].sort((a, b) => a.stepOrder - b.stepOrder)
}

// The step's own `stepOrder`/`totalSteps` can reference a stale snapshot of
// the category's workflow (confirmed live 2026-09-14: a brand-new invitation
// submitted well after a category was edited down from 2 levels to 1 still
// came back with a 2-step snapshot). Once the category's *live* rules are
// loaded, prefer finding this step's role by position within them instead of
// trusting the raw `stepOrder` — that's the category's real, current level
// count and ordering. Falls back to the raw (possibly stale) `stepOrder`
// when live rules aren't loaded yet, or the step's role isn't found among
// them (e.g. that role was since removed from the category).
export function resolveCurrentLevel(
  step: CurrentApprovalStep | null | undefined,
  visitorCategoryId: string | null | undefined,
  workflowRulesByCategory: Record<string, ApprovalWorkflowRule[]>,
): number {
  if (!step) return 1

  const sorted = sortedRulesFor(visitorCategoryId, workflowRulesByCategory)
  if (sorted && step.approverRoleId) {
    const index = sorted.findIndex((rule) => rule.approverRoleId === step.approverRoleId)
    if (index !== -1) return index + 1
  }

  return displayStepLevel(step.stepOrder)
}

// Whether `step` is the workflow's first configured level (Reception) —
// derived from `resolveCurrentLevel` so it stays consistent with the level
// number actually shown, rather than trusting the step's own (possibly
// stale) `stepOrder` independently.
export function isReceptionCurrentStep(
  step: CurrentApprovalStep | null | undefined,
  visitorCategoryId: string | null | undefined,
  workflowRulesByCategory: Record<string, ApprovalWorkflowRule[]>,
): boolean {
  if (!step) return false
  return resolveCurrentLevel(step, visitorCategoryId, workflowRulesByCategory) === 1
}

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

// `CurrentApprovalStep.totalSteps` is a backend-supplied value that can go
// stale relative to the visitor category's *current* workflow config (e.g.
// captured when the invitation entered the workflow, before an admin edited
// the category's level count, or from the stale-snapshot bug noted above).
// The workflow rules list for the invitation's category — already fetched
// and defensively re-filtered by `ensureWorkflowRulesLoaded` for the
// "Pending:" preview below — reflects the category's actual level count
// right now, so prefer its length once loaded and fall back to the backend
// value otherwise (e.g. before rules load).
//
// The live count can also be *smaller* than the invitation's own real step
// count, though — an in-flight invitation submitted while the category still
// had more levels legitimately has more real steps than the category's
// current config, and is still working through them. Never show a level
// number greater than the total ("Level 3 of 2" is nonsensical) — floor the
// result at the current step's own (role-matched, see `resolveCurrentLevel`)
// display level.
export function resolveTotalSteps(
  detail: InvitationDetail,
  workflowRulesByCategory: Record<string, ApprovalWorkflowRule[]>,
): number {
  const rules = detail.visitorCategoryId ? workflowRulesByCategory[detail.visitorCategoryId] : undefined
  const baseline = rules && rules.length > 0 ? rules.length : (detail.currentApprovalStep?.totalSteps ?? 1)
  const currentLevel = resolveCurrentLevel(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory)
  return Math.max(baseline, currentLevel)
}

// The invitation's workflow has exactly one level (Reception, stepOrder 0 —
// enforced by `lock-workflow-level-one-to-reception`), mirroring the same
// "reception-only" condition `VisitRequestCard`'s plain "Approve" button uses
// (`isReceptionApprovalStep && totalSteps <= 1`), so this never disagrees
// with which invitations actually get the plain-Approve action instead of
// "Approve & Delegate".
export function resolvePointOfContactLabel(
  detail: InvitationDetail,
  workflowRulesByCategory: Record<string, ApprovalWorkflowRule[]>,
): string | undefined {
  if (!isReceptionCurrentStep(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory)) {
    return undefined
  }
  return resolveTotalSteps(detail, workflowRulesByCategory) <= 1 ? 'Reception' : undefined
}

// On Reception's own step in a multi-step workflow, "Pending:" should
// preview the *next* step's role rather than naming Reception's own step
// (redundant to the person already looking at their own queue). Returns
// `undefined` for every other case — a non-Reception step, a single-step
// (Reception-only) workflow, an invitation with no visitor category, rules
// not yet cached for that category, or no resolvable next-step role — so the
// caller falls back to `resolveApproverLabel` unchanged.
export function resolveNextStepPreviewLabel(
  detail: InvitationDetail,
  workflowRulesByCategory: Record<string, ApprovalWorkflowRule[]>,
  roleNameById: Record<string, string>,
): string | undefined {
  const step = detail.currentApprovalStep
  if (!step || step.totalSteps <= 1 || !detail.visitorCategoryId) {
    return undefined
  }

  const sorted = sortedRulesFor(detail.visitorCategoryId, workflowRulesByCategory)
  if (!sorted) return undefined

  const currentIndex = step.approverRoleId ? sorted.findIndex((rule) => rule.approverRoleId === step.approverRoleId) : -1
  if (currentIndex !== 0) return undefined // only preview ahead from Reception's own (first) step

  const nextRule = sorted[currentIndex + 1]
  return nextRule ? roleNameById[nextRule.approverRoleId] : undefined
}
