import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { LIVE_REFRESH_INTERVAL_MS, usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { ApprovalWorkflowRule } from '../../../../domain/entities/approval-workflow-rule-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

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
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listApprovalWorkflowRulesUseCase, listVisitorCategoriesUseCase, listRolesUseCase, deleteWorkflowUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [workflows, setWorkflows] = useState<WorkflowGroup[]>([])
  const [categoryOptions, setCategoryOptions] = useState<{ value: string; label: string }[]>([])
  const { phase, isRefreshing, begin } = useLoadTracker()

  const [pendingDelete, setPendingDelete] = useState<WorkflowGroup | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  // `user` (default): filter/retry/refresh/post-delete - keeps the current
  // rows on screen with a progress cue. `background`: the 15s poll.
  const loadWorkflows = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, rules, categories, roles] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listApprovalWorkflowRulesUseCase.execute({
            visitorCategoryId: categoryFilter || undefined,
            status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
          }),
          listVisitorCategoriesUseCase.execute(),
          listRolesUseCase.execute(),
        ])
        if (!request.succeed()) return
        setCurrentUser(user)

        const categoryNameById = new Map(categories.map((category) => [category.id, category.name]))
        const roleNameById = new Map(roles.map((role) => [role.id, role.name]))
        setCategoryOptions(categories.map((category) => ({ value: category.id, label: category.name })).sort((a, b) => a.label.localeCompare(b.label)))

        const rulesByCategory = new Map<string, ApprovalWorkflowRule[]>()
        for (const rule of rules) {
          const group = rulesByCategory.get(rule.visitorCategoryId) ?? []
          group.push(rule)
          rulesByCategory.set(rule.visitorCategoryId, group)
        }

        const groups: WorkflowGroup[] = Array.from(rulesByCategory.entries()).map(([visitorCategoryId, categoryRules]) => {
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

        setWorkflows(groups)
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the workflows. Please try again.')
      }
    },
    [
      begin,
      getCurrentStaffUserUseCase,
      listApprovalWorkflowRulesUseCase,
      listVisitorCategoriesUseCase,
      listRolesUseCase,
      categoryFilter,
      statusFilter,
      toast,
    ],
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
  usePolling(() => void loadWorkflows('background'), { intervalMs: LIVE_REFRESH_INTERVAL_MS, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing })

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
      await loadWorkflows()
    } catch {
      toast.error('Something went wrong deleting the workflow. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteWorkflowUseCase, toast, loadWorkflows, resetToFirstPage])

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
