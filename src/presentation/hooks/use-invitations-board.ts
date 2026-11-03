import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useAppDependencies } from '../context/app-dependencies-context'
import { useCurrentUser } from '../context/current-user-context'
import { useToast } from '../components/toast/toast-context'
import { ApiError } from '../../data/api/api-error'
import { useLiveResource } from './use-live-resource'
import { useDebouncedValue } from './use-debounced-value'
import { isReceptionCurrentStep, resolveApproverLabel, resolveCurrentLevel, resolveTotalSteps } from '../utils/approval-step-label'
import { employeeAtBranch, employeeHasRoleAtBranch } from '../utils/role-name-match'
import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'
import type { CurrentApprovalStep, InvitationDetail } from '../../domain/entities/invitation-detail-schema'
import type { RoleOut } from '../../domain/entities/role-out-schema'
import type { HostEmployee } from '../../domain/entities/host-employee-schema'
import type { ApprovalWorkflowRule } from '../../domain/entities/approval-workflow-rule-schema'
import type { EditInvitationFields, InvitationDrillDown } from '../../data/repositories/visit-request-summary-repository'
import { drillDownChips, parseDeepLinkStatuses, parseDrillDown } from '../components/invitation-board/board-drill-down'
import { PURPOSE_OF_VISIT_OPTIONS, purposeStoredValues } from '../utils/purpose-of-visit-options'
import { saveBlob } from '../utils/save-blob'
import { REGISTRATION_TYPE_OPTIONS, SOURCE_OPTIONS, exportFilename, optionLabel } from '../components/invitation-board/filter-options'
import type { InvitationExportChoice } from '../components/invitation-board/ExportInvitationsModal'
import { boardStatusForApiStatus, usePagedBoardColumns, type BoardStatus, type ColumnQuery } from './use-paged-board-columns'
import { permissionsFor } from '../utils/permissions'

const EMPTY_ROLES: RoleOut[] = []
const EMPTY_EMPLOYEES: HostEmployee[] = []

export const BOARD_STATUS_COLUMNS = [
  { status: 'requested', label: 'Requested' },
  { status: 'approved', label: 'Approved' },
  { status: 'checked_in', label: 'Checked-in' },
  { status: 'checked_out', label: 'Checked-out' },
  { status: 'denied', label: 'Denied' },
  // Approved visitors who never arrived; the API's visit-lifecycle sweep moves
  // them here the day after their visit (VMSS_API auto-checkout-and-archive-no-shows).
  { status: 'archived', label: 'Archived' },
] as const satisfies ReadonlyArray<{ status: BoardStatus; label: string }>

const ALL_BOARD_STATUSES: readonly BoardStatus[] = BOARD_STATUS_COLUMNS.map((column) => column.status)

// Mostly look-up statuses, grouped into one Closed column on desktop
// (staff-dashboard "Closed statuses share one column on desktop").
export const CLOSED_BOARD_STATUSES: readonly BoardStatus[] = ['checked_out', 'denied', 'archived']

// Toast copy for an approve action: names which level just cleared and,
// unless this was the final one, who the request is now waiting on.
function describeApprovalOutcome(
  approvedStep: CurrentApprovalStep,
  nextStep: CurrentApprovalStep | null,
  roleNameById: Record<string, string>,
  employeeNameById: Record<string, string>,
  totalSteps: number,
  visitorCategoryId: string | null | undefined,
  workflowRulesByCategory: Record<string, ApprovalWorkflowRule[]>,
): string {
  const approvedLevel = resolveCurrentLevel(approvedStep, visitorCategoryId, workflowRulesByCategory)
  if (!nextStep) {
    return `Level ${approvedLevel} of ${totalSteps} approved — request fully approved.`
  }

  const approverLabel = resolveApproverLabel(nextStep, roleNameById, employeeNameById)
  const nextLevel = resolveCurrentLevel(nextStep, visitorCategoryId, workflowRulesByCategory)
  return `Level ${approvedLevel} of ${totalSteps} approved — now waiting on ${approverLabel} (level ${nextLevel} of ${totalSteps}).`
}

// Shared Kanban-board data/actions behind the staff dashboard and the admin
// invitations board — same columns, same approve/reschedule/step-progress
// behavior, differing in scope: the staff dashboard asks the API for only the requests where the
// current user is the host or a delegate (`relevantToMe=true`), while the
// admin board keeps its organisation-wide view. Every filter is applied
// server-side, per status column (see `usePagedBoardColumns`).
export function useInvitationsBoard(scope: 'mine' | 'all' = 'all') {
  const [searchParams] = useSearchParams()
  const {
    listVisitRequestsUseCase,
    approveInvitationUseCase,
    getInvitationDetailUseCase,
    listRolesUseCase,
    listHostEmployeesUseCase,
    rescheduleInvitationUseCase,
    editInvitationUseCase,
    denyInvitationUseCase,
    revertInvitationApprovalUseCase,
    checkOutInvitationUseCase,
    exportInvitationsUseCase,
    approveInvitationStepUseCase,
    rejectInvitationStepUseCase,
    delegateInvitationStepUseCase,
    listApprovalWorkflowRulesUseCase,
    listBranchesUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()
  // Filter/search changes reload only the columns (not the whole board), so
  // they're tracked separately; a count, since a newer filter change can
  // start before an older one settles.
  const [pendingColumnReloads, setPendingColumnReloads] = useState(0)
  const [search, setSearch] = useState('')
  const [purposeFilter, setPurposeFilter] = useState<string[]>([])
  const [registrationTypeFilter, setRegistrationTypeFilter] = useState<string[]>([])
  // A dashboard tile, bar or "View all" link opens the board on exactly what
  // it counted: one or more ?status=<api status> plus the drill-down params
  // (visit dates, upcoming, not expired, branch), applied once on load.
  // Unknown or malformed values are ignored (staff-dashboard /
  // admin-invitations "opens a status from a deep link").
  const [statusFilter, setStatusFilter] = useState<string[]>(() => parseDeepLinkStatuses(searchParams))
  const [drillDown, setDrillDown] = useState<InvitationDrillDown>(() => parseDrillDown(searchParams))
  const [drillDownBranchName, setDrillDownBranchName] = useState<string | undefined>(undefined)
  const [sourceFilter, setSourceFilter] = useState<string[]>([])
  const debouncedSearch = useDebouncedValue(search, 300)
  const [approvingId, setApprovingId] = useState<string | undefined>(undefined)
  const [pendingApproveId, setPendingApproveId] = useState<string | undefined>(undefined)
  const [pendingRevertId, setPendingRevertId] = useState<string | undefined>(undefined)
  const [revertingId, setRevertingId] = useState<string | undefined>(undefined)
  const [invitationDetails, setInvitationDetails] = useState<Record<string, InvitationDetail>>({})
  const [reschedulingId, setReschedulingId] = useState<string | undefined>(undefined)
  const [delegatingId, setDelegatingId] = useState<string | undefined>(undefined)
  const [editingId, setEditingId] = useState<string | undefined>(undefined)
  const [pendingDenyId, setPendingDenyId] = useState<string | undefined>(undefined)
  const [denyingId, setDenyingId] = useState<string | undefined>(undefined)
  const [pendingCheckOutId, setPendingCheckOutId] = useState<string | undefined>(undefined)
  const [checkingOutId, setCheckingOutId] = useState<string | undefined>(undefined)
  const [pendingRescheduleId, setPendingRescheduleId] = useState<string | undefined>(undefined)
  const [pendingDelegateId, setPendingDelegateId] = useState<string | undefined>(undefined)
  const [approvingAndDelegatingId, setApprovingAndDelegatingId] = useState<string | undefined>(undefined)
  const [pendingApproveAndDelegateId, setPendingApproveAndDelegateId] = useState<string | undefined>(undefined)
  const [nextStepCandidates, setNextStepCandidates] = useState<HostEmployee[]>([])
  const [workflowRulesByCategory, setWorkflowRulesByCategory] = useState<Record<string, ApprovalWorkflowRule[]>>({})
  const [isLoadingNextStepCandidates, setIsLoadingNextStepCandidates] = useState(false)
  const [pendingEditId, setPendingEditId] = useState<string | undefined>(undefined)
  const [visitorInfoId, setVisitorInfoId] = useState<string | undefined>(undefined)
  const [visitorInfo, setVisitorInfo] = useState<{ status: 'loading' | 'ready' | 'error'; detail?: InvitationDetail }>({ status: 'loading' })
  const [isExportOpen, setIsExportOpen] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [exportError, setExportError] = useState<string | undefined>(undefined)
  const isExportingRef = useRef(false)

  const columnQuery = useMemo<ColumnQuery>(
    () => ({
      relevantToMe: scope === 'mine',
      registrationTypes: registrationTypeFilter,
      sources: sourceFilter,
      search: debouncedSearch.trim() || undefined,
      purposesOfVisit: purposeFilter.flatMap(purposeStoredValues),
      ...drillDown,
    }),
    [scope, registrationTypeFilter, sourceFilter, debouncedSearch, purposeFilter, drillDown],
  )
  // Owned here, not by either page, so the staff and admin bars share one
  // definition of "a filter is set" and of what Clear filters resets.
  const isFiltering =
    purposeFilter.length > 0 ||
    statusFilter.length > 0 ||
    registrationTypeFilter.length > 0 ||
    sourceFilter.length > 0 ||
    Object.keys(drillDown).length > 0
  // Leaves the search text alone - only the dropdown filters and the
  // dashboard chips reset.
  const clearFilters = useCallback(() => {
    setPurposeFilter([])
    setStatusFilter([])
    setRegistrationTypeFilter([])
    setSourceFilter([])
    setDrillDown({})
  }, [])

  // The branch chip shows a name, not an id; the board stays usable (with a
  // generic label) if the branch list can't be loaded.
  const drillDownBranchId = drillDown.branchId
  useEffect(() => {
    if (!drillDownBranchId) return
    let isCurrent = true
    listBranchesUseCase
      .execute()
      .then((branches) => {
        if (isCurrent) setDrillDownBranchName(branches.find((branch) => branch.id === drillDownBranchId)?.name)
      })
      .catch((error: unknown) => console.error('Failed to load the branch name for the board filter', error))
    return () => {
      isCurrent = false
    }
  }, [drillDownBranchId, listBranchesUseCase])

  const dashboardChips = useMemo(
    () =>
      drillDownChips(drillDown, drillDownBranchName).map((chip) => ({
        key: chip.keys.join('+'),
        label: chip.label,
        onRemove: () =>
          setDrillDown((current) => {
            const next = { ...current }
            for (const key of chip.keys) delete next[key]
            return next
          }),
      })),
    [drillDown, drillDownBranchName],
  )
  // A status filter narrows loading to that one column; a status with no
  // column leaves every column empty.
  const visibleStatuses = useMemo<readonly BoardStatus[]>(() => {
    if (statusFilter.length === 0) return ALL_BOARD_STATUSES
    return statusFilter.flatMap((apiStatus) => boardStatusForApiStatus(apiStatus) ?? [])
  }, [statusFilter])

  // A closed status chosen in the filter should be the one the Closed column shows.
  const focusClosedStatus = useMemo(() => {
    return visibleStatuses.find((status) => statusFilter.length > 0 && CLOSED_BOARD_STATUSES.includes(status))
  }, [statusFilter, visibleStatuses])

  const fetchVisitRequestsPage = useCallback(
    (params: Parameters<typeof listVisitRequestsUseCase.execute>[0]) => listVisitRequestsUseCase.execute(params),
    [listVisitRequestsUseCase],
  )
  const {
    columns: columnPages,
    reload: reloadColumns,
    loadMore,
  } = usePagedBoardColumns(fetchVisitRequestsPage, columnQuery, visibleStatuses)

  // progress, so the auto-refresh tick can skip a fetch that would otherwise
  // disrupt it.
  const isActionInProgress =
    pendingApproveId !== undefined ||
    approvingId !== undefined ||
    pendingRevertId !== undefined ||
    revertingId !== undefined ||
    pendingDenyId !== undefined ||
    pendingRescheduleId !== undefined ||
    pendingDelegateId !== undefined ||
    pendingEditId !== undefined ||
    pendingApproveAndDelegateId !== undefined ||
    pendingCheckOutId !== undefined ||
    denyingId !== undefined ||
    checkingOutId !== undefined ||
    reschedulingId !== undefined ||
    delegatingId !== undefined ||
    editingId !== undefined ||
    approvingAndDelegatingId !== undefined

  // Every reload keeps each column's loaded depth (refresh, polling, and the
  // reload after an action); only a filter/search change resets columns to
  // their first page (the effect below). After the first load the columns
  // stay mounted through every reload - a `user` reload only adds the
  // in-progress cue - so they keep their scroll position. Roles and host
  // employees (names, pickers) load once per visit, not on every poll, and
  // only a failed first load or manual refresh toasts (design D-W4).
  const board = useLiveResource({
    load: () => reloadColumns({ keepDepth: true }),
    reference: async () => {
      const [roles, employees] = await Promise.all([
        // Listing roles is admin-scoped and 403s for other staff roles
        // (e.g. host, reception). Every consumer of roleNameById already
        // falls back gracefully when a name is missing (see
        // resolveApproverLabel), so degrade to an empty list here instead
        // of failing the whole reference load over a permission the
        // current user was never going to have.
        listRolesUseCase.execute().catch(() => [] as RoleOut[]),
        listHostEmployeesUseCase.execute(),
      ])
      return { roles, employees }
    },
    errorMessage: 'Something went wrong loading the dashboard. Please try again.',
    isBusy: isActionInProgress,
    // The pages register the top-bar refresh, with the filter reloads folded
    // into `isRefreshing`.
    registerRefresh: false,
  })
  const { phase, isRefreshing: isReloadingBoard, hasFailed, retry: refresh, reload: loadDashboard } = board
  const roles = board.reference?.roles ?? EMPTY_ROLES
  const hostEmployees = board.reference?.employees ?? EMPTY_EMPLOYEES
  const roleNameById = useMemo(() => Object.fromEntries(roles.map((role) => [role.id, role.name])) as Record<string, string>, [roles])
  const employeeNameById = useMemo(
    () => Object.fromEntries(hostEmployees.map((employee) => [employee.id, employee.fullName])) as Record<string, string>,
    [hostEmployees],
  )

  // A changed filter or (debounced) search restarts every column from its
  // first page. Skipped on mount - the initial board load covers that.
  // The cards on screen stay put, dimmed under the progress bar, until the
  // filtered columns replace them (async-ui-states "Re-fetching keeps
  // existing content visible").
  const hasAppliedInitialQueryRef = useRef(false)
  useEffect(() => {
    if (!hasAppliedInitialQueryRef.current) {
      hasAppliedInitialQueryRef.current = true
      return
    }
    setPendingColumnReloads((count) => count + 1)
    reloadColumns({ keepDepth: false })
      .catch((error: unknown) => {
        console.error('Failed to apply board filters', error)
        toast.error('Something went wrong loading the dashboard. Please try again.')
      })
      .finally(() => setPendingColumnReloads((count) => count - 1))
  }, [columnQuery, visibleStatuses, reloadColumns, toast])

  const isRefreshing = isReloadingBoard || pendingColumnReloads > 0

  // Workflow rules are defined per visitor category, not per invitation, so
  // every card sharing a category reuses one fetch instead of one each. The
  // in-flight/resolved promise is cached (not just a "have we started"
  // flag) so a caller that needs the rules immediately after triggering a
  // load (e.g. `loadNextStepCandidates` below) can await the same fetch and
  // get the real result, instead of racing the `workflowRulesByCategory`
  // state update.
  const workflowRulesPromiseCacheRef = useRef<Record<string, Promise<ApprovalWorkflowRule[]>>>({})
  const ensureWorkflowRulesLoaded = useCallback(
    (visitorCategoryId: string): Promise<ApprovalWorkflowRule[]> => {
      const cached = workflowRulesPromiseCacheRef.current[visitorCategoryId]
      if (cached) return cached

      const promise = listApprovalWorkflowRulesUseCase
        .execute({ visitorCategoryId })
        .then((rules) => {
          // Don't trust the backend to have actually filtered by the query
          // param — `use-admin-workflow-form.ts` doesn't (it fetches broadly
          // and filters client-side), so mirror that here defensively. An
          // unfiltered response would otherwise let a same-stepOrder rule
          // from a different category silently win the lookup below. Also
          // drop any `isActive: false` row still coming back from the API
          // (e.g. a level removed in the workflow editor that the backend
          // didn't actually delete) — otherwise `resolveTotalSteps` counts it
          // and shows one level more than is really configured.
          const scopedRules = rules.filter((rule) => rule.visitorCategoryId === visitorCategoryId && rule.isActive)
          setWorkflowRulesByCategory((previous) => ({ ...previous, [visitorCategoryId]: scopedRules }))
          return scopedRules
        })
        .catch((error: unknown) => {
          console.error('Failed to load workflow rules for visitor category', error)
          delete workflowRulesPromiseCacheRef.current[visitorCategoryId]
          // A role without list-rules permission (e.g. host/reception hitting
          // the admin-only `approval-workflow-rules` 403, see memory) would
          // otherwise leave `workflowRulesByCategory[id]` `undefined` forever,
          // which `VisitRequestCard`'s `workflowRulesLoaded` treats as
          // "still loading" — permanently disabling drag-to-approve with no
          // explanation. Record the failed attempt as an empty result (unless
          // a prior successful load already populated real rules) so the UI
          // falls back to the step's own raw `stepOrder`/`totalSteps`
          // snapshot instead of blocking approval entirely.
          setWorkflowRulesByCategory((previous) => ({ ...previous, [visitorCategoryId]: previous[visitorCategoryId] ?? [] }))
          throw error
        })

      workflowRulesPromiseCacheRef.current[visitorCategoryId] = promise
      return promise
    },
    [listApprovalWorkflowRulesUseCase],
  )

  // Preloads workflow rules for every visible card with a live approval step,
  // so "Pending:" can preview the next level and the level/total badges can
  // use the category's *current* rules instead of the step's own possibly
  // stale `stepOrder`/`totalSteps` snapshot (confirmed backend bug: a fresh
  // invitation can still snapshot an outdated version of the category's
  // workflow). Deliberately not gated on `step.stepOrder === 0` (Reception) —
  // that raw value is exactly what can be stale — nor on `step.totalSteps > 1`:
  // a single-level category can still snapshot a non-zero `stepOrder` for its
  // one (Reception) step. The cards read the step from their list item, so
  // this is one rules request per visitor category, never one per card
  // (design D12).
  useEffect(() => {
    const categoryIdsNeedingRules = new Set<string>()

    for (const request of [...columnPages.requested.items, ...columnPages.approved.items]) {
      if (request.currentApprovalStep && request.visitorCategoryId && !workflowRulesPromiseCacheRef.current[request.visitorCategoryId]) {
        categoryIdsNeedingRules.add(request.visitorCategoryId)
      }
    }

    categoryIdsNeedingRules.forEach((categoryId) => {
      // `ensureWorkflowRulesLoaded` already logs and rethrows on failure (e.g.
      // a 403 for a role without list-rules permission) so its own caller can
      // react; this background preload has no caller to react, so swallow it
      // here instead of leaving an unhandled rejection in the console.
      ensureWorkflowRulesLoaded(categoryId).catch(() => {})
    })
  }, [columnPages.requested.items, columnPages.approved.items, ensureWorkflowRulesLoaded])

  // The full detail is fetched only when an action or dialog needs it, and
  // always fresh: the board moves on between polls, and cards no longer
  // preload it (design D12).
  const loadDetail = useCallback(
    async (id: string): Promise<InvitationDetail> => {
      const detail = await getInvitationDetailUseCase.execute(id)
      setInvitationDetails((previous) => ({ ...previous, [id]: detail }))
      return detail
    },
    [getInvitationDetailUseCase],
  )

  // Opens the "Visitor Info" popup for a card with its own loading and error
  // state per open. It never shows an earlier fetch of the same invitation:
  // the photo URLs are short-lived signed links, so a detail fetched minutes
  // ago would render broken images.
  const visitorInfoRequestRef = useRef(0)
  const fetchVisitorInfo = useCallback(
    (id: string) => {
      const requestId = ++visitorInfoRequestRef.current
      setVisitorInfo({ status: 'loading' })
      loadDetail(id)
        .then((detail) => {
          if (requestId === visitorInfoRequestRef.current) setVisitorInfo({ status: 'ready', detail })
        })
        .catch((error: unknown) => {
          console.error('Failed to load visitor info', error)
          if (requestId === visitorInfoRequestRef.current) setVisitorInfo({ status: 'error' })
        })
    },
    [loadDetail],
  )

  const viewVisitorInfo = useCallback(
    (id: string) => {
      setVisitorInfoId(id)
      fetchVisitorInfo(id)
    },
    [fetchVisitorInfo],
  )

  const retryVisitorInfo = useCallback(() => {
    if (visitorInfoId) fetchVisitorInfo(visitorInfoId)
  }, [visitorInfoId, fetchVisitorInfo])

  const closeVisitorInfo = useCallback(() => {
    visitorInfoRequestRef.current += 1
    setVisitorInfoId(undefined)
  }, [])

  // Opens the invitation named by ?invitationId=... (e.g. from a clicked push
  // notification) the same way clicking its card does, once on mount.
  const hasOpenedDeepLinkRef = useRef(false)
  useEffect(() => {
    if (hasOpenedDeepLinkRef.current) return
    const invitationId = searchParams.get('invitationId')
    if (!invitationId) return

    hasOpenedDeepLinkRef.current = true
    viewVisitorInfo(invitationId)
  }, [searchParams, viewVisitorInfo])

  const approve = useCallback(
    async (id: string) => {
      setApprovingId(id)

      try {
        const detail = await loadDetail(id)

        if (detail.currentApprovalStep) {
          // Mirrors `delegate`'s guard below, for the opposite mistake: when
          // more than one level is configured, Reception must go through
          // "Approve & Delegate" so the next level actually gets created —
          // a plain approve here (e.g. a drag-and-drop drop onto "Approved")
          // would finalize Reception's step as if it were the last one,
          // silently skipping the remaining levels. The UI already disables
          // dragging and hides the plain "Approve" button for this case, but
          // that depends on `isReceptionCurrentStep`/`resolveTotalSteps`
          // having correctly loaded, live workflow-rules data by the time the
          // card rendered — this check enforces the rule regardless of that.
          if (
            isReceptionCurrentStep(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory) &&
            resolveTotalSteps(detail, workflowRulesByCategory) > 1
          ) {
            throw new Error('Reception must use "Approve & Delegate" when more than one approval level is configured.')
          }

          await approveInvitationStepUseCase.execute(id, detail.currentApprovalStep.id)
          const updatedDetail = await getInvitationDetailUseCase.execute(id)
          setInvitationDetails((previous) => ({ ...previous, [id]: updatedDetail }))
          toast.success(
            describeApprovalOutcome(
              detail.currentApprovalStep,
              updatedDetail.currentApprovalStep,
              roleNameById,
              employeeNameById,
              resolveTotalSteps(detail, workflowRulesByCategory),
              detail.visitorCategoryId,
              workflowRulesByCategory,
            ),
          )
        } else {
          await approveInvitationUseCase.execute(id)
          toast.success('Visit request approved.')
        }

        await loadDashboard('background')
      } catch (error) {
        console.error('Failed to approve visit request', error)
        toast.error(error instanceof Error ? error.message : 'Failed to approve the visit request. Please try again.')
      } finally {
        setApprovingId(undefined)
      }
    },
    [
      approveInvitationUseCase,
      approveInvitationStepUseCase,
      getInvitationDetailUseCase,
      loadDashboard,
      loadDetail,
      roleNameById,
      employeeNameById,
      workflowRulesByCategory,
      toast,
    ],
  )

  // Any card currently loaded on the board, whichever column it's in — lets
  // every action's confirmation name the visitor and REQ ID it acts on.
  const findRequest = useCallback(
    (id: string | undefined): VisitRequestSummary | undefined => {
      if (!id) return undefined
      for (const page of Object.values(columnPages)) {
        const match = page.items.find((request) => request.id === id)
        if (match) return match
      }
      return undefined
    },
    [columnPages],
  )

  // Approve (card button or drop) only opens the confirmation; the request
  // goes out from `confirmApprove`.
  const requestApprove = useCallback((id: string) => {
    setPendingApproveId(id)
  }, [])

  const cancelApprove = useCallback(() => {
    setPendingApproveId(undefined)
  }, [])

  const confirmApprove = useCallback(async () => {
    if (!pendingApproveId || approvingId) return
    await approve(pendingApproveId)
    setPendingApproveId(undefined)
  }, [pendingApproveId, approvingId, approve])

  const reschedule = useCallback(
    async (id: string, preferredVisitDate: string, preferredVisitTime: string) => {
      setReschedulingId(id)
      // Rescheduling an archived no-show sends it back for approval rather
      // than keeping it approved, so the toast says so.
      const wasArchived = findRequest(id)?.status === 'archived'

      try {
        await rescheduleInvitationUseCase.execute(id, preferredVisitDate, preferredVisitTime)
        setPendingRescheduleId(undefined)
        toast.success(wasArchived ? 'Visit rescheduled — awaiting re-approval.' : 'Visit request rescheduled.')
        await loadDashboard('background')
      } catch (error) {
        console.error('Failed to reschedule visit request', error)
        toast.error(error instanceof Error ? error.message : 'Failed to reschedule the visit request. Please try again.')
      } finally {
        setReschedulingId(undefined)
      }
    },
    [rescheduleInvitationUseCase, findRequest, loadDashboard, toast],
  )

  const requestReschedule = useCallback((id: string) => {
    setPendingRescheduleId(id)
  }, [])

  const cancelReschedule = useCallback(() => {
    setPendingRescheduleId(undefined)
  }, [])

  // Reassigns the current pending approval step to a different person — the
  // delegate target is always a specific host/employee, whether picked
  // directly or narrowed down via another role's roster.
  const delegate = useCallback(
    async (id: string, delegateUserId: string) => {
      setDelegatingId(id)

      try {
        const detail = await loadDetail(id)
        if (!detail.currentApprovalStep) {
          throw new Error('This request has no pending approval step to delegate.')
        }
        if (isReceptionCurrentStep(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory)) {
          throw new Error('Reception must approve this request before it can be delegated to another step.')
        }

        await delegateInvitationStepUseCase.execute(id, detail.currentApprovalStep.id, delegateUserId)
        const updatedDetail = await getInvitationDetailUseCase.execute(id)
        setInvitationDetails((previous) => ({ ...previous, [id]: updatedDetail }))
        setPendingDelegateId(undefined)

        const approverLabel = employeeNameById[delegateUserId] ?? 'the selected host'
        const delegatedLevel = resolveCurrentLevel(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory)
        toast.success(`Delegated level ${delegatedLevel} of ${resolveTotalSteps(detail, workflowRulesByCategory)} to ${approverLabel}.`)

        await loadDashboard('background')
      } catch (error) {
        console.error('Failed to delegate approval step', error)
        toast.error(error instanceof Error ? error.message : 'Failed to delegate this approval step. Please try again.')
      } finally {
        setDelegatingId(undefined)
      }
    },
    [delegateInvitationStepUseCase, getInvitationDetailUseCase, loadDashboard, loadDetail, employeeNameById, workflowRulesByCategory, toast],
  )

  // The dialog filters candidates by the current step's role and branch, so
  // it needs the detail, fetched fresh on open (cards no longer preload it).
  const requestDelegate = useCallback(
    (id: string) => {
      setPendingDelegateId(id)
      void loadDetail(id).catch((error: unknown) => {
        console.error('Failed to load invitation detail for delegate', error)
        toast.error('Could not load this request for delegating.')
        setPendingDelegateId(undefined)
      })
    },
    [loadDetail, toast],
  )

  const cancelDelegate = useCallback(() => {
    setPendingDelegateId(undefined)
  }, [])

  const pendingDelegateDetail = pendingDelegateId ? invitationDetails[pendingDelegateId] : undefined

  // Populates the "Approve & Delegate" dropdown with employees eligible for
  // the *next* step — not the current (Reception) step's role. The next
  // step's role isn't on the invitation detail itself, so this additionally
  // consults the workflow's configured rules for the invitation's visitor
  // category, same data `admin-workflows` already uses.
  const loadNextStepCandidates = useCallback(
    async (id: string) => {
      setIsLoadingNextStepCandidates(true)
      setNextStepCandidates([])

      try {
        const detail = await loadDetail(id)
        const step = detail.currentApprovalStep
        if (!step || step.totalSteps <= 1 || !detail.visitorCategoryId) {
          return
        }

        // Find the current step's role by *position* among the category's
        // live rules, then take the one right after it — not `stepOrder`
        // arithmetic, since the step's own `stepOrder` can be a stale
        // snapshot (confirmed backend bug) that no longer lines up with the
        // category's current rule ordering.
        let nextRoleName: string | undefined
        try {
          const rules = await ensureWorkflowRulesLoaded(detail.visitorCategoryId)
          const sortedRules = [...rules].sort((a, b) => a.stepOrder - b.stepOrder)
          const currentIndex = step.approverRoleId ? sortedRules.findIndex((rule) => rule.approverRoleId === step.approverRoleId) : -1
          const nextRule = currentIndex !== -1 ? sortedRules[currentIndex + 1] : undefined
          nextRoleName = nextRule ? roleNameById[nextRule.approverRoleId] : undefined
        } catch (error) {
          // `approval-workflow-rules` is admin-scoped and 403s for host/reception
          // (see `ensureWorkflowRulesLoaded`'s own comment). Without the rules we
          // can't know exactly which role handles the next step, so fall through
          // to offering every active employee at the branch below instead of
          // leaving this picker permanently empty — the backend still enforces
          // the real role-at-branch check when the delegate is submitted.
          console.error('Could not resolve the next approval step role', error)
        }

        setNextStepCandidates(
          nextRoleName
            ? hostEmployees.filter((employee) => employeeHasRoleAtBranch(employee, nextRoleName, detail.branchId))
            : hostEmployees.filter((employee) => employeeAtBranch(employee, detail.branchId)),
        )
      } catch (error) {
        console.error('Failed to load next-step candidates', error)
        toast.error('Could not load eligible employees for the next step.')
      } finally {
        setIsLoadingNextStepCandidates(false)
      }
    },
    [loadDetail, ensureWorkflowRulesLoaded, roleNameById, hostEmployees, toast],
  )

  const requestApproveAndDelegate = useCallback(
    (id: string) => {
      setPendingApproveAndDelegateId(id)
      void loadNextStepCandidates(id)
    },
    [loadNextStepCandidates],
  )

  const cancelApproveAndDelegate = useCallback(() => {
    setPendingApproveAndDelegateId(undefined)
    setNextStepCandidates([])
  }, [])

  const pendingApproveAndDelegateDetail = pendingApproveAndDelegateId ? invitationDetails[pendingApproveAndDelegateId] : undefined

  // Approves Reception's own (first-level) step and assigns a specific
  // employee to the resulting next step, in one user-facing action. Once the
  // approve call succeeds it cannot be undone (no "unapprove" operation
  // exists), so a failure in the delegate call that follows is reported
  // distinctly from a failure in the approve call itself — see design.md's
  // partial-failure decision.
  const approveAndDelegate = useCallback(
    async (id: string, delegateUserId: string) => {
      setApprovingAndDelegatingId(id)

      try {
        const detail = await loadDetail(id)
        if (!detail.currentApprovalStep || !isReceptionCurrentStep(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory)) {
          throw new Error('This request is not pending Reception approval.')
        }

        await approveInvitationStepUseCase.execute(id, detail.currentApprovalStep.id)

        try {
          const updatedDetail = await getInvitationDetailUseCase.execute(id)
          setInvitationDetails((previous) => ({ ...previous, [id]: updatedDetail }))

          const totalSteps = resolveTotalSteps(detail, workflowRulesByCategory)
          const approvedLevel = resolveCurrentLevel(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory)
          if (!updatedDetail.currentApprovalStep) {
            toast.success(`Level ${approvedLevel} of ${totalSteps} approved — request fully approved.`)
          } else {
            await delegateInvitationStepUseCase.execute(id, updatedDetail.currentApprovalStep.id, delegateUserId)
            const finalDetail = await getInvitationDetailUseCase.execute(id)
            setInvitationDetails((previous) => ({ ...previous, [id]: finalDetail }))
            const approverLabel = employeeNameById[delegateUserId] ?? 'the selected employee'
            const nextLevel = resolveCurrentLevel(updatedDetail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory)
            toast.success(
              `Level ${approvedLevel} of ${totalSteps} approved — now assigned to ${approverLabel} (level ${nextLevel} of ${totalSteps}).`,
            )
          }

          setPendingApproveAndDelegateId(undefined)
          setNextStepCandidates([])
        } catch (error) {
          console.error('Approved, but failed to assign the next approver', error)
          toast.error(
            error instanceof Error
              ? `Request approved, but could not assign the next approver: ${error.message}`
              : 'Request approved, but the next approver could not be assigned. Please delegate manually.',
          )
        }
      } catch (error) {
        console.error('Failed to approve visit request', error)
        toast.error(error instanceof Error ? error.message : 'Failed to approve the visit request. Please try again.')
      } finally {
        await loadDashboard('background')
        setApprovingAndDelegatingId(undefined)
      }
    },
    [
      approveInvitationStepUseCase,
      getInvitationDetailUseCase,
      delegateInvitationStepUseCase,
      loadDetail,
      loadDashboard,
      employeeNameById,
      workflowRulesByCategory,
      toast,
    ],
  )

  // Opening the modal fetches the detail itself, like Delegate: cards don't
  // preload it.
  const requestEdit = useCallback(
    (id: string) => {
      setPendingEditId(id)
      void loadDetail(id).catch((error: unknown) => {
        console.error('Failed to load invitation detail for edit', error)
        toast.error('Could not load this request for editing.')
        setPendingEditId(undefined)
      })
    },
    [loadDetail, toast],
  )

  const cancelEdit = useCallback(() => {
    setPendingEditId(undefined)
  }, [])

  const pendingEditDetail = pendingEditId ? invitationDetails[pendingEditId] : undefined

  const edit = useCallback(
    async (id: string, fields: EditInvitationFields) => {
      setEditingId(id)

      try {
        await editInvitationUseCase.execute(id, fields)
        const updatedDetail = await getInvitationDetailUseCase.execute(id)
        setInvitationDetails((previous) => ({ ...previous, [id]: updatedDetail }))
        setPendingEditId(undefined)
        toast.success('Visit request updated.')
        await loadDashboard('background')
      } catch (error) {
        console.error('Failed to edit visit request', error)
        toast.error(error instanceof Error ? error.message : 'Failed to update the visit request. Please try again.')
      } finally {
        setEditingId(undefined)
      }
    },
    [editInvitationUseCase, getInvitationDetailUseCase, loadDashboard, toast],
  )

  const requestDeny = useCallback((id: string) => {
    setPendingDenyId(id)
  }, [])

  const cancelDeny = useCallback(() => {
    setPendingDenyId(undefined)
  }, [])

  const confirmDeny = useCallback(
    async (reason: string) => {
      if (!pendingDenyId) return
      const id = pendingDenyId

      setDenyingId(id)

      try {
        const detail = await loadDetail(id)

        if (detail.currentApprovalStep) {
          await rejectInvitationStepUseCase.execute(id, detail.currentApprovalStep.id, reason)
          const deniedLevel = resolveCurrentLevel(detail.currentApprovalStep, detail.visitorCategoryId, workflowRulesByCategory)
          toast.success(`Denied at level ${deniedLevel} of ${resolveTotalSteps(detail, workflowRulesByCategory)}.`)
        } else {
          await denyInvitationUseCase.execute(id, reason)
          toast.success('Visit request denied.')
        }

        setPendingDenyId(undefined)
        await loadDashboard('background')
      } catch (error) {
        console.error('Failed to deny visit request', error)
        toast.error(error instanceof Error ? error.message : 'Failed to deny the visit request. Please try again.')
      } finally {
        setDenyingId(undefined)
      }
    },
    [pendingDenyId, denyInvitationUseCase, rejectInvitationStepUseCase, loadDashboard, loadDetail, workflowRulesByCategory, toast],
  )

  // Shown to every board user: the web app has no permission codes, and only
  // Security lacks `invitations:revert-approval` by default — the API's 403
  // is the real authority.
  const requestRevert = useCallback((id: string) => {
    setPendingRevertId(id)
  }, [])

  const cancelRevert = useCallback(() => {
    setPendingRevertId(undefined)
  }, [])

  // Resolves whether the dialog closed. A 409 means the visit is no longer
  // revertible (re-approved elsewhere, or the visitor already scanned in), so
  // the dialog closes and the board reloads to show where the card is now;
  // any other failure keeps the dialog — and the typed reason — for a retry.
  const confirmRevert = useCallback(
    async (reason: string): Promise<boolean> => {
      if (!pendingRevertId || revertingId) return false
      const id = pendingRevertId
      const visitorName = findRequest(id)?.primaryContactFullName

      setRevertingId(id)

      try {
        await revertInvitationApprovalUseCase.execute(id, reason)
        toast.success(visitorName ? `Approval reverted for ${visitorName}.` : 'Approval reverted.')
        setPendingRevertId(undefined)
        setInvitationDetails((previous) => {
          const { [id]: _stale, ...rest } = previous
          return rest
        })
        await loadDashboard('background')
        return true
      } catch (error) {
        console.error('Failed to revert approval', error)
        toast.error(error instanceof Error ? error.message : 'Failed to revert the approval. Please try again.')
        if (error instanceof ApiError && error.status === 409) {
          setPendingRevertId(undefined)
          await loadDashboard('background')
          return true
        }
        return false
      } finally {
        setRevertingId(undefined)
      }
    },
    [pendingRevertId, revertingId, findRequest, revertInvitationApprovalUseCase, loadDashboard, toast],
  )

  // Which actions the board offers, by the caller's permission codes (design
  // D-W1), so a tenant-defined role gets exactly the buttons its grants
  // allow. The API stays the authority; this only hides what would 403.
  const permissions = useMemo(() => permissionsFor(currentUser), [currentUser])
  const actionPermissions = useMemo(
    () => ({
      approve: permissions.can('invitations:approve'),
      deny: permissions.can('invitations:deny'),
      // Delegating hands an approval step on, so it rides on approving.
      delegate: permissions.can('invitations:approve'),
      revert: permissions.can('invitations:revert-approval'),
      edit: permissions.can('invitations:edit'),
      reschedule: permissions.can('invitations:reschedule'),
    }),
    [permissions],
  )
  const canCheckOut = permissions.can('invitations:checkout')
  const canExport = permissions.can('invitations:export')

  // What the export applies beyond the dialog's own status/dates/format,
  // as shown read-only in the dialog — the same values `columnQuery` sends.
  const exportFilterSummary = useMemo(() => {
    const summary: string[] = []
    if (columnQuery.search) summary.push(`Search: "${columnQuery.search}"`)
    if (purposeFilter.length > 0) summary.push(`Purpose: ${purposeFilter.join(', ')}`)
    if (registrationTypeFilter.length > 0) {
      summary.push(`Type: ${registrationTypeFilter.map((value) => optionLabel(REGISTRATION_TYPE_OPTIONS, value)).join(', ')}`)
    }
    if (sourceFilter.length > 0) summary.push(`Source: ${sourceFilter.map((value) => optionLabel(SOURCE_OPTIONS, value)).join(', ')}`)
    for (const chip of dashboardChips) summary.push(chip.label)
    return summary
  }, [columnQuery.search, purposeFilter, registrationTypeFilter, sourceFilter, dashboardChips])

  // The export endpoint takes one value per filter and returns a file that
  // can't be merged client-side, so several values must be narrowed first.
  const exportNeedsNarrowing = [purposeFilter, registrationTypeFilter, sourceFilter, statusFilter].some((values) => values.length > 1)

  const openExport = useCallback(() => {
    setExportError(undefined)
    setIsExportOpen(true)
  }, [])

  const closeExport = useCallback(() => {
    if (isExportingRef.current) return
    setIsExportOpen(false)
    setExportError(undefined)
  }, [])

  const exportInvitations = useCallback(
    async (choice: InvitationExportChoice) => {
      // A ref, not `isExporting`: two clicks in one tick would both see the
      // stale state value and start two downloads.
      if (isExportingRef.current) return
      isExportingRef.current = true
      setIsExporting(true)
      setExportError(undefined)
      try {
        const blob = await exportInvitationsUseCase.execute({
          relevantToMe: columnQuery.relevantToMe,
          search: columnQuery.search,
          purposeOfVisit: purposeFilter[0],
          registrationType: registrationTypeFilter[0],
          source: sourceFilter[0],
          status: choice.status || undefined,
          dateFrom: choice.dateFrom || undefined,
          dateTo: choice.dateTo || undefined,
          format: choice.format,
          ...drillDown,
        })
        saveBlob(blob, exportFilename(choice.status, choice.format))
        setIsExportOpen(false)
        toast.success('Export downloaded.')
      } catch (error) {
        // Kept inside the dialog (not a toast) so the user can narrow the
        // filters and retry without re-entering their choices.
        setExportError(error instanceof Error ? error.message : 'Something went wrong exporting invitations. Please try again.')
      } finally {
        isExportingRef.current = false
        setIsExporting(false)
      }
    },
    [columnQuery.relevantToMe, columnQuery.search, purposeFilter, registrationTypeFilter, sourceFilter, drillDown, exportInvitationsUseCase, toast],
  )

  const requestCheckOut = useCallback((id: string) => {
    setPendingCheckOutId(id)
  }, [])

  const cancelCheckOut = useCallback(() => {
    setPendingCheckOutId(undefined)
  }, [])

  const pendingCheckOutRequest = useMemo(
    () => (pendingCheckOutId ? columnPages.checked_in.items.find((request) => request.id === pendingCheckOutId) : undefined),
    [pendingCheckOutId, columnPages],
  )

  const confirmCheckOut = useCallback(async () => {
    if (!pendingCheckOutId || checkingOutId) return
    const id = pendingCheckOutId
    const visitorName = pendingCheckOutRequest?.primaryContactFullName

    setCheckingOutId(id)

    try {
      // One key per confirmation: a network-level retry of this same request
      // replays the cached result instead of hitting a 409.
      await checkOutInvitationUseCase.execute(id, crypto.randomUUID())
      toast.success(visitorName ? `${visitorName} checked out.` : 'Visitor checked out.')
    } catch (error) {
      console.error('Failed to check out visitor', error)
      toast.error(error instanceof Error ? error.message : 'Failed to check out the visitor. Please try again.')
    } finally {
      setPendingCheckOutId(undefined)
      setCheckingOutId(undefined)
    }
    // Reload on failure too: a 409 usually means a QR exit scan already
    // moved the card, so the board should show where it actually is now.
    await loadDashboard('background')
  }, [pendingCheckOutId, checkingOutId, pendingCheckOutRequest, checkOutInvitationUseCase, loadDashboard, toast])

  // Filtered server-side by exact match, and invitations hold the purpose as
  // either its display name ("Interview") or its option slug ("interview"),
  // so each selected label is queried under both (`purposeStoredValues`).
  const purposeOptions = useMemo(
    () => PURPOSE_OF_VISIT_OPTIONS.map(({ label }) => ({ value: label, label })),
    [],
  )

  const columns = useMemo(
    () =>
      BOARD_STATUS_COLUMNS.map((column) => {
        const page = columnPages[column.status]
        return {
          ...column,
          requests: page.items,
          total: page.total,
          hasMore: page.items.length < page.total,
          isLoadingMore: page.isLoadingMore,
          loadMoreFailed: page.loadMoreFailed,
          resetKey: page.resetKey,
          loadMore: () => void loadMore(column.status),
        }
      }),
    [columnPages, loadMore],
  )

  return {
    currentUser,
    columns,
    phase,
    search,
    setSearch,
    purposeFilter,
    setPurposeFilter,
    purposeOptions,
    registrationTypeFilter,
    setRegistrationTypeFilter,
    setStatusFilter,
    sourceFilter,
    setSourceFilter,
    isFiltering,
    clearFilters,
    refresh,
    isRefreshing,
    approve,
    approvingId,
    findRequest,
    pendingApproveId,
    requestApprove,
    cancelApprove,
    confirmApprove,
    pendingRevertId,
    requestRevert,
    cancelRevert,
    confirmRevert,
    revertingId,
    invitationDetails,
    visitorInfo,
    retryVisitorInfo,
    hasFailed,
    roles,
    roleNameById,
    hostEmployees,
    employeeNameById,
    reschedule,
    reschedulingId,
    delegate,
    delegatingId,
    edit,
    editingId,
    requestEdit,
    cancelEdit,
    pendingEditId,
    pendingEditDetail,
    pendingDenyId,
    requestDeny,
    cancelDeny,
    confirmDeny,
    denyingId,
    canCheckOut,
    canExport,
    actionPermissions,
    isExportOpen,
    openExport,
    closeExport,
    exportInvitations,
    isExporting,
    exportError,
    exportFilterSummary,
    exportNeedsNarrowing,
    statusFilter,
    dashboardChips,
    focusClosedStatus,
    pendingCheckOutId,
    pendingCheckOutRequest,
    requestCheckOut,
    cancelCheckOut,
    confirmCheckOut,
    checkingOutId,
    pendingRescheduleId,
    requestReschedule,
    cancelReschedule,
    pendingDelegateId,
    requestDelegate,
    cancelDelegate,
    pendingDelegateDetail,
    approveAndDelegate,
    approvingAndDelegatingId,
    pendingApproveAndDelegateId,
    requestApproveAndDelegate,
    cancelApproveAndDelegate,
    pendingApproveAndDelegateDetail,
    nextStepCandidates,
    isLoadingNextStepCandidates,
    workflowRulesByCategory,
    visitorInfoId,
    viewVisitorInfo,
    closeVisitorInfo,
  }
}
