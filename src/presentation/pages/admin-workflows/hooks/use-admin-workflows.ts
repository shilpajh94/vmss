import { useCallback, useMemo, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { ApprovalWorkflowRule } from '../../../../domain/entities/approval-workflow-rule-schema'
import { toUserMessage } from '../../../utils/to-user-message'

export interface WorkflowLevelView {
  ruleId: string
  stepOrder: number
  approverRoleId: string
  approverRoleName: string
  isActive: boolean
}

export type WorkflowStatus = 'active' | 'paused'

export interface WorkflowGroup {
  visitorCategoryId: string
  categoryName: string
  levels: WorkflowLevelView[]
  status: WorkflowStatus
}

const PAGE_SIZE = 4

export function useAdminWorkflows() {
  const { listApprovalWorkflowRulesUseCase, listVisitorCategoriesUseCase, listRolesUseCase, deleteWorkflowUseCase } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()

  const [pendingDelete, setPendingDelete] = useState<WorkflowGroup | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // The rules are the live data; category and role names load once (and on
  // a manual refresh). Polls skip while a delete dialog is open.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  const resource = useLiveResource({
    load: () =>
      listApprovalWorkflowRulesUseCase.execute({
        visitorCategoryId: categoryFilter || undefined,
        status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
      }),
    query: { categoryFilter, statusFilter },
    reference: async () => {
      const [categories, roles] = await Promise.all([listVisitorCategoriesUseCase.execute(), listRolesUseCase.execute()])
      return { categories, roles }
    },
    errorMessage: 'Something went wrong loading the workflows. Please try again.',
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, reload } = resource

  const categoryOptions = useMemo(
    () =>
      (resource.reference?.categories ?? [])
        .map((category) => ({ value: category.id, label: category.name }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [resource.reference],
  )

  const workflows = useMemo<WorkflowGroup[]>(() => {
    const categoryNameById = new Map((resource.reference?.categories ?? []).map((category) => [category.id, category.name]))
    const roleNameById = new Map((resource.reference?.roles ?? []).map((role) => [role.id, role.name]))

    const rulesByCategory = new Map<string, ApprovalWorkflowRule[]>()
    for (const rule of resource.data ?? []) {
      const group = rulesByCategory.get(rule.visitorCategoryId) ?? []
      group.push(rule)
      rulesByCategory.set(rule.visitorCategoryId, group)
    }

    return Array.from(rulesByCategory.entries()).map(([visitorCategoryId, categoryRules]) => {
      const levels: WorkflowLevelView[] = [...categoryRules]
        .sort((a, b) => a.stepOrder - b.stepOrder)
        .map((rule) => ({
          ruleId: rule.id,
          stepOrder: rule.stepOrder,
          approverRoleId: rule.approverRoleId,
          approverRoleName: roleNameById.get(rule.approverRoleId) ?? 'Unknown role',
          isActive: rule.isActive,
        }))

      return {
        visitorCategoryId,
        categoryName: categoryNameById.get(visitorCategoryId) ?? 'Unknown category',
        levels,
        status: levels.every((level) => level.isActive) ? 'active' : ('paused' as WorkflowStatus),
      }
    })
  }, [resource.data, resource.reference])

  const isFiltering = categoryFilter !== '' || statusFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  const changeCategoryFilter = useCallback(
    (value: string) => {
      setCategoryFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const changeStatusFilter = useCallback(
    (value: string) => {
      setStatusFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const clearFilters = useCallback(() => {
    setCategoryFilter('')
    setStatusFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

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
      toast.success('Workflow deleted.')
      setPendingDelete(undefined)
      resetToFirstPage()
      await reload()
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong deleting the workflow. Please try again.'))
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteWorkflowUseCase, toast, reload, resetToFirstPage])

  const totalPages = Math.max(1, Math.ceil(workflows.length / PAGE_SIZE))
  const pagedWorkflows = workflows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return {
    currentUser,
    workflows,
    pagedWorkflows,
    page,
    pageSize: PAGE_SIZE,
    totalPages,
    goToPreviousPage: goToPrevPage,
    goToNextPage,
    phase,
    isRefreshing,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    categoryOptions,
    categoryFilter,
    setCategoryFilter: changeCategoryFilter,
    statusFilter,
    setStatusFilter: changeStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
