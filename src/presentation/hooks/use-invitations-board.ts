import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useAppDependencies } from '../context/app-dependencies-context'
import { useToast } from '../components/toast/toast-context'
import { ApiError } from '../../data/api/api-error'
import { usePolling } from './use-polling'
import { useDebouncedValue } from './use-debounced-value'
import { isReceptionCurrentStep, resolveApproverLabel, resolveCurrentLevel, resolveTotalSteps } from '../utils/approval-step-label'
import { employeeAtBranch, employeeHasRoleAtBranch } from '../utils/role-name-match'
import type { StaffUser } from '../../domain/entities/staff-user-schema'
import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'
import type { CurrentApprovalStep, InvitationDetail } from '../../domain/entities/invitation-detail-schema'
import type { RoleOut } from '../../domain/entities/role-out-schema'
import type { HostEmployee } from '../../domain/entities/host-employee-schema'
import type { ApprovalWorkflowRule } from '../../domain/entities/approval-workflow-rule-schema'
import type { EditInvitationFields } from '../../data/repositories/visit-request-summary-repository'
import { PURPOSE_OF_VISIT_OPTIONS } from '../utils/purpose-of-visit-options'
import { saveBlob } from '../utils/save-blob'
import { REGISTRATION_TYPE_OPTIONS, SOURCE_OPTIONS, exportFilename, optionLabel } from '../components/invitation-board/filter-options'
import type { InvitationExportChoice } from '../components/invitation-board/ExportInvitationsModal'
import { boardStatusForApiStatus, usePagedBoardColumns, type BoardStatus, type ColumnQuery } from './use-paged-board-columns'

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
// behavior, differing in where an unauthenticated visitor is redirected and
// in scope: the staff dashboard asks the API for only the requests where the
// current user is the host or a delegate (`relevantToMe=true`), while the
// admin board keeps its organisation-wide view. Every filter is applied
// server-side, per status column (see `usePagedBoardColumns`).
export function useInvitationsBoard(loginRedirectPath: string, scope: 'mine' | 'all' = 'all') {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const {
    listVisitRequestsUseCase,
    approveInvitationUseCase,
    getCurrentStaffUserUseCase,
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
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [roles, setRoles] = useState<RoleOut[]>([])
  const [roleNameById, setRoleNameById] = useState<Record<string, string>>({})
  const [hostEmployees, setHostEmployees] = useState<HostEmployee[]>([])
  const [employeeNameById, setEmployeeNameById] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [search, setSearch] = useState('')
  const [purposeFilter, setPurposeFilter] = useState('all')
  const [registrationTypeFilter, setRegistrationTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)
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
  const [isExportOpen, setIsExportOpen] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [exportError, setExportError] = useState<string | undefined>(undefined)
  const isExportingRef = useRef(false)

  const columnQuery = useMemo<ColumnQuery>(
    () => ({
      relevantToMe: scope === 'mine',
      registrationType: registrationTypeFilter === 'all' ? undefined : registrationTypeFilter,
      source: sourceFilter || undefined,
      search: debouncedSearch.trim() || undefined,
      purposeOfVisit: purposeFilter === 'all' ? undefined : purposeFilter,
    }),
    [scope, registrationTypeFilter, sourceFilter, debouncedSearch, purposeFilter],
  )
  // A status filter (admin board) narrows loading to that one column; a
  // status with no column leaves every column empty.
  const visibleStatuses = useMemo<readonly BoardStatus[]>(() => {
    if (!statusFilter) return ALL_BOARD_STATUSES
    const status = boardStatusForApiStatus(statusFilter)
    return status ? [status] : []
  }, [statusFilter])

  const fetchVisitRequestsPage = useCallback(
    (params: Parameters<typeof listVisitRequestsUseCase.execute>[0]) => listVisitRequestsUseCase.execute(params),
    [listVisitRequestsUseCase],
  )
  const {
    columns: columnPages,
    reload: reloadColumns,
    loadMore,
  } = usePagedBoardColumns(fetchVisitRequestsPage, columnQuery, visibleStatuses)

  // Every reload keeps each column's loaded depth (refresh, polling, and the
  // reload after an action); only a filter/search change resets columns to
  // their first page (the effect below). `silent` skips the full-board
  // loading state, which would otherwise unmount the columns and lose their
  // scroll position.
  const loadDashboard = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, , roles, employees] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          reloadColumns({ keepDepth: true }),
          // Listing roles is admin-scoped and 403s for other staff roles
          // (e.g. host, reception). Every consumer of roleNameById already
          // falls back gracefully when a name is missing (see
          // resolveApproverLabel), so degrade to an empty list here instead
          // of failing the whole dashboard load over a permission the
          // current user was never going to have.
          listRolesUseCase.execute().catch((error: unknown) => {
            console.error('Failed to load roles', error)
            return []
          }),
          listHostEmployeesUseCase.execute(),
        ])
        setCurrentUser(user)
        setRoles(roles)
        setRoleNameById(Object.fromEntries(roles.map((role: RoleOut) => [role.id, role.name])))
        setHostEmployees(employees)
        setEmployeeNameById(Object.fromEntries(employees.map((employee) => [employee.id, employee.fullName])))
        setLastUpdatedAt(new Date())
      } catch (error) {
        console.error('Failed to load dashboard', error)
        if (!silent) {
          setErrorMessage('Something went wrong loading the dashboard. Please try again.')
        }
        toast.error('Something went wrong loading the dashboard. Please try again.')
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [getCurrentStaffUserUseCase, reloadColumns, listRolesUseCase, listHostEmployeesUseCase, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate(loginRedirectPath, { replace: true })
      return
    }

    void loadDashboard()
  }, [navigate, loginRedirectPath, loadDashboard])

  // A changed filter or (debounced) search restarts every column from its
  // first page. Skipped on mount - the initial `loadDashboard` covers that.
  const hasAppliedInitialQueryRef = useRef(false)
  useEffect(() => {
    if (!hasAppliedInitialQueryRef.current) {
      hasAppliedInitialQueryRef.current = true
      return
    }
    reloadColumns({ keepDepth: false }).catch((error: unknown) => {
      console.error('Failed to apply board filters', error)
      toast.error('Something went wrong loading the dashboard. Please try again.')
    })
  }, [columnQuery, visibleStatuses, reloadColumns, toast])

  const refresh = useCallback(() => {
    setIsRefreshing(true)
    void loadDashboard({ silent: true }).finally(() => setIsRefreshing(false))
  }, [loadDashboard])

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

  usePolling(() => void loadDashboard({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

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

  // Preloads approval-step detail for pending requests so the "Level X/Y"
  // badge is visible on the collapsed card, not just after expanding it.
  // Runs only for cards actually loaded into the Requested/Approved columns,
  // so lazy loading caps it at one page's worth per scroll.
  //
  // Kicks off the category's workflow-rules fetch (below) in parallel with
  // the detail fetch, keyed off the summary's own `visitorCategoryId` rather
  // than waiting for the detail to resolve first: chaining them was exactly
  // what caused the card to render once with the stale `stepOrder`/`totalSteps`
  // snapshot and then "blink" to the correct level 2-3s later once the
  // category's live rules arrived on their own separate round trip.
  const pendingDetailFetchesRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    const requestsNeedingDetail = [...columnPages.requested.items, ...columnPages.approved.items].filter(
      (request) => !invitationDetails[request.id] && !pendingDetailFetchesRef.current.has(request.id),
    )

    requestsNeedingDetail.forEach((request) => {
      const id = request.id
      pendingDetailFetchesRef.current.add(id)
      getInvitationDetailUseCase
        .execute(id)
        .then((detail) => {
          setInvitationDetails((previous) => ({ ...previous, [id]: detail }))
        })
        .catch((error: unknown) => {
          console.error('Failed to preload approval progress', error)
        })
        .finally(() => {
          pendingDetailFetchesRef.current.delete(id)
        })

      if (request.visitorCategoryId) {
        ensureWorkflowRulesLoaded(request.visitorCategoryId).catch(() => {})
      }
    })
  }, [columnPages.requested.items, columnPages.approved.items, invitationDetails, getInvitationDetailUseCase, ensureWorkflowRulesLoaded])

  // Preloads workflow rules for every visible card with a live approval step,
  // so "Pending:" can preview the next level and the level/total badges can
  // use the category's *current* rules instead of the step's own possibly
  // stale `stepOrder`/`totalSteps` snapshot (confirmed backend bug: a fresh
  // invitation can still snapshot an outdated version of the category's
  // workflow). Deliberately not gated on `step.stepOrder === 0` (Reception) —
  // that raw value is exactly what can be stale — nor on `step.totalSteps > 1`:
  // a single-level category can still snapshot a non-zero `stepOrder` for its
  // one (Reception) step, and `totalSteps` claiming "1" was exactly what
  // used to skip this preload, leaving `resolveCurrentLevel` stuck on that
  // stale `stepOrder` fallback forever (confirmed live: shows "Level 2/2" on
  // a freshly-created, never-edited single-level category). Every step needs
  // the live rules to display correctly, not just ones whose snapshot
  // happens to already look ambiguous.
  useEffect(() => {
    const categoryIdsNeedingRules = new Set<string>()

    for (const detail of Object.values(invitationDetails)) {
      const step = detail.currentApprovalStep
      if (step && detail.visitorCategoryId && !workflowRulesPromiseCacheRef.current[detail.visitorCategoryId]) {
        categoryIdsNeedingRules.add(detail.visitorCategoryId)
      }
    }

    categoryIdsNeedingRules.forEach((categoryId) => {
      // `ensureWorkflowRulesLoaded` already logs and rethrows on failure (e.g.
      // a 403 for a role without list-rules permission) so its own caller can
      // react; this background preload has no caller to react, so swallow it
      // here instead of leaving an unhandled rejection in the console.
      ensureWorkflowRulesLoaded(categoryId).catch(() => {})
    })
  }, [invitationDetails, ensureWorkflowRulesLoaded])

  const loadDetail = useCallback(
    async (id: string, options?: { forceRefresh?: boolean }): Promise<InvitationDetail> => {
      if (!options?.forceRefresh && invitationDetails[id]) return invitationDetails[id]

      const detail = await getInvitationDetailUseCase.execute(id)
      setInvitationDetails((previous) => ({ ...previous, [id]: detail }))
      return detail
    },
    [invitationDetails, getInvitationDetailUseCase],
  )

  // Opens the "Visitor Info" popup for a card, fetching the full invitation
  // detail (GET /invitations/:id). Always forces a fresh fetch (unlike the
  // approval-progress preload above, which is fine reusing a cached detail):
  // the response's primary/visitor photo URLs are short-lived signed links
  // (see visit-tracking-repository.ts's backend counterpart), so a detail
  // fetched more than a few minutes ago would render broken images if reused.
  const viewVisitorInfo = useCallback(
    (id: string) => {
      setVisitorInfoId(id)
      void loadDetail(id, { forceRefresh: true }).catch((error: unknown) => {
        console.error('Failed to load visitor info', error)
        toast.error('Could not load visitor info for this request.')
      })
    },
    [loadDetail, toast],
  )

  const closeVisitorInfo = useCallback(() => {
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

        await loadDashboard({ silent: true })
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
        await loadDashboard({ silent: true })
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

        await loadDashboard({ silent: true })
      } catch (error) {
        console.error('Failed to delegate approval step', error)
        toast.error(error instanceof Error ? error.message : 'Failed to delegate this approval step. Please try again.')
      } finally {
        setDelegatingId(undefined)
      }
    },
    [delegateInvitationStepUseCase, getInvitationDetailUseCase, loadDashboard, loadDetail, employeeNameById, workflowRulesByCategory, toast],
  )

  const requestDelegate = useCallback((id: string) => {
    setPendingDelegateId(id)
  }, [])

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
        await loadDashboard({ silent: true })
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

  // Unlike Delegate (only offered once a card's detail is already loaded,
  // since `canDelegate` depends on `detail.currentApprovalStep`), Edit is
  // offered purely by status — a card whose detail was never fetched (e.g.
  // an "approved" column card never expanded) can still show the button.
  // So opening the modal has to fetch detail itself rather than assume it's
  // already in `invitationDetails`.
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
        await loadDashboard({ silent: true })
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
        await loadDashboard({ silent: true })
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
        await loadDashboard({ silent: true })
        return true
      } catch (error) {
        console.error('Failed to revert approval', error)
        toast.error(error instanceof Error ? error.message : 'Failed to revert the approval. Please try again.')
        if (error instanceof ApiError && error.status === 409) {
          setPendingRevertId(undefined)
          await loadDashboard({ silent: true })
          return true
        }
        return false
      } finally {
        setRevertingId(undefined)
      }
    },
    [pendingRevertId, revertingId, findRequest, revertInvitationApprovalUseCase, loadDashboard, toast],
  )

  // Only Admin and Reception hold `invitations:checkout` by default; the web
  // app has no permission codes, so this role-name check decides whether the
  // Checked-in column gets the button and the API stays the real authority.
  const canCheckOut = Boolean(currentUser?.isAdmin || currentUser?.isReception)

  // `invitations:export` is granted to Admin and Reception (and Security,
  // which has no board). Same role-name stand-in as `canCheckOut`: the admin
  // board is Admin-only, and on the staff dashboard only Reception gets it —
  // a host would just get a 403.
  const canExport = scope === 'all' ? Boolean(currentUser?.isAdmin) : Boolean(currentUser?.isReception)

  // What the export applies beyond the dialog's own status/dates/format,
  // as shown read-only in the dialog — the same values `columnQuery` sends.
  const exportFilterSummary = useMemo(() => {
    const summary: string[] = []
    if (columnQuery.search) summary.push(`Search: "${columnQuery.search}"`)
    if (columnQuery.purposeOfVisit) summary.push(`Purpose: ${columnQuery.purposeOfVisit}`)
    if (columnQuery.registrationType) summary.push(`Type: ${optionLabel(REGISTRATION_TYPE_OPTIONS, columnQuery.registrationType)}`)
    if (columnQuery.source) summary.push(`Source: ${optionLabel(SOURCE_OPTIONS, columnQuery.source)}`)
    return summary
  }, [columnQuery])

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
          ...columnQuery,
          status: choice.status || undefined,
          dateFrom: choice.dateFrom || undefined,
          dateTo: choice.dateTo || undefined,
          format: choice.format,
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
    [columnQuery, exportInvitationsUseCase, toast],
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
    await loadDashboard({ silent: true })
  }, [pendingCheckOutId, checkingOutId, pendingCheckOutRequest, checkOutInvitationUseCase, loadDashboard, toast])

  // Filtered server-side by exact match, and the wizards store the purpose's
  // display name ("Interview"), not the option slug ("interview") - so the
  // label is what gets sent.
  const purposeOptions = useMemo(
    () => [{ value: 'all', label: 'All purposes' }, ...PURPOSE_OF_VISIT_OPTIONS.map(({ label }) => ({ value: label, label }))],
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
    isLoading,
    errorMessage,
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
    lastUpdatedAt,
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
    isExportOpen,
    openExport,
    closeExport,
    exportInvitations,
    isExporting,
    exportError,
    exportFilterSummary,
    statusFilter,
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
