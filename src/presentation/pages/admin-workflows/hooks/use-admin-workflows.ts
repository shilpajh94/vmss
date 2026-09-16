import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import type { ApprovalWorkflowRule } from '../../../../domain/entities/approval-workflow-rule-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export interface WorkflowLevelView {
  ruleId: string
  stepOrder: number
  approverRoleId: string
  approverRoleName: string
}

export interface WorkflowGroup {
  visitorCategoryId: string
  categoryName: string
  levels: WorkflowLevelView[]
}

export function useAdminWorkflows() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listApprovalWorkflowRulesUseCase, listVisitorCategoriesUseCase, listRolesUseCase, deleteWorkflowUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [workflows, setWorkflows] = useState<WorkflowGroup[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<WorkflowGroup | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const loadWorkflows = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, rules, categories, roles] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listApprovalWorkflowRulesUseCase.execute(),
          listVisitorCategoriesUseCase.execute(),
          listRolesUseCase.execute(),
        ])
        setCurrentUser(user)

        const categoryNameById = new Map(categories.map((category) => [category.id, category.name]))
        const roleNameById = new Map(roles.map((role) => [role.id, role.name]))

        const rulesByCategory = new Map<string, ApprovalWorkflowRule[]>()
        for (const rule of rules) {
          const group = rulesByCategory.get(rule.visitorCategoryId) ?? []
          group.push(rule)
          rulesByCategory.set(rule.visitorCategoryId, group)
        }

        const groups: WorkflowGroup[] = Array.from(rulesByCategory.entries()).map(([visitorCategoryId, categoryRules]) => ({
          visitorCategoryId,
          categoryName: categoryNameById.get(visitorCategoryId) ?? 'Unknown category',
          levels: [...categoryRules]
            .sort((a, b) => a.stepOrder - b.stepOrder)
            .map((rule) => ({
              ruleId: rule.id,
              stepOrder: rule.stepOrder,
              approverRoleId: rule.approverRoleId,
              approverRoleName: roleNameById.get(rule.approverRoleId) ?? 'Unknown role',
            })),
        }))

        setWorkflows(groups)
      } catch {
        if (!silent) {
          setErrorMessage('Something went wrong loading the workflows. Please try again.')
        }
        toast.error('Something went wrong loading the workflows. Please try again.')
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [getCurrentStaffUserUseCase, listApprovalWorkflowRulesUseCase, listVisitorCategoriesUseCase, listRolesUseCase, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadWorkflows()
  }, [navigate, loadWorkflows])

  const retry = useCallback(() => {
    void loadWorkflows()
  }, [loadWorkflows])

  const isActionInProgress = pendingDelete !== undefined || isDeleting
  usePolling(() => void loadWorkflows({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

  const requestDelete = useCallback((workflow: WorkflowGroup) => {
    setPendingDelete(workflow)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteWorkflowUseCase.execute(pendingDelete.levels.map((level) => level.ruleId))
      setWorkflows((current) => current.filter((workflow) => workflow.visitorCategoryId !== pendingDelete.visitorCategoryId))
      toast.success('Workflow deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the workflow. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteWorkflowUseCase, toast])

  return {
    currentUser,
    workflows,
    isLoading,
    errorMessage,
    retry,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
