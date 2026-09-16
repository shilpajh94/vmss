import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useAppDependencies } from '../context/app-dependencies-context'
import { useToast } from '../components/toast/toast-context'
import { isReceptionCurrentStep, resolveApproverLabel, resolveCurrentLevel, resolveTotalSteps } from '../utils/approval-step-label'
import { employeeHasRoleAtBranch } from '../utils/role-name-match'
import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'
import type { StaffUser } from '../../domain/entities/staff-user-schema'
import type { CurrentApprovalStep, InvitationDetail } from '../../domain/entities/invitation-detail-schema'
import type { RoleOut } from '../../domain/entities/role-out-schema'
import type { HostEmployee } from '../../domain/entities/host-employee-schema'
import type { ApprovalWorkflowRule } from '../../domain/entities/approval-workflow-rule-schema'
import type { EditInvitationFields } from '../../data/repositories/visit-request-summary-repository'
import { PURPOSE_OF_VISIT_OPTIONS } from '../utils/purpose-of-visit-options'

export const BOARD_STATUS_COLUMNS = [
  { status: 'requested', label: 'Requested' },
  { status: 'approved', label: 'Approved' },
  { status: 'checked_in', label: 'Checked-in' },
  { status: 'denied', label: 'Denied' },
] as const

// Maps raw API `status` values to the columns above.
// TODO: only "submitted" -> "requested" is confirmed against real API data so far;
// the approved/checked_in/denied wire values still need verifying against the backend.
const STATUS_ALIASES: Record<string, (typeof BOARD_STATUS_COLUMNS)[number]['status']> = {
  submitted: 'requested',
}

function normalizeStatus(status: string): string {
  return STATUS_ALIASES[status] ?? status
}

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
// admin board keeps its organisation-wide view.
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
    approveInvitationStepUseCase,
    rejectInvitationStepUseCase,
    delegateInvitationStepUseCase,
    listApprovalWorkflowRulesUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [visitRequests, setVisitRequests] = useState<VisitRequestSummary[]>([])
  const [roles, setRoles] = useState<RoleOut[]>([])
  const [roleNameById, setRoleNameById] = useState<Record<string, string>>({})
  const [hostEmployees, setHostEmployees] = useState<HostEmployee[]>([])
  const [employeeNameById, setEmployeeNameById] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [search, setSearch] = useState('')
  const [purposeFilter, setPurposeFilter] = useState('all')
  const [registrationTypeFilter, setRegistrationTypeFilter] = useState('all')
  const [approvingId, setApprovingId] = useState<string | undefined>(undefined)
  const [expandedId, setExpandedId] = useState<string | undefined>(undefined)
  const [invitationDetails, setInvitationDetails] = useState<Record<string, InvitationDetail>>({})
  const [loadingDetailId, setLoadingDetailId] = useState<string | undefined>(undefined)
  const [reschedulingId, setReschedulingId] = useState<string | undefined>(undefined)
  const [delegatingId, setDelegatingId] = useState<string | undefined>(undefined)
  const [editingId, setEditingId] = useState<string | undefined>(undefined)
  const [pendingDenyId, setPendingDenyId] = useState<string | undefined>(undefined)
  const [denyingId, setDenyingId] = useState<string | undefined>(undefined)
  const [pendingRescheduleId, setPendingRescheduleId] = useState<string | undefined>(undefined)
  const [pendingDelegateId, setPendingDelegateId] = useState<string | undefined>(undefined)
  const [approvingAndDelegatingId, setApprovingAndDelegatingId] = useState<string | undefined>(undefined)
  const [pendingApproveAndDelegateId, setPendingApproveAndDelegateId] = useState<string | undefined>(undefined)
  const [nextStepCandidates, setNextStepCandidates] = useState<HostEmployee[]>([])
  const [workflowRulesByCategory, setWorkflowRulesByCategory] = useState<Record<string, ApprovalWorkflowRule[]>>({})
  const [isLoadingNextStepCandidates, setIsLoadingNextStepCandidates] = useState(false)
  const [pendingEditId, setPendingEditId] = useState<string | undefined>(undefined)
  const [visitorInfoId, setVisitorInfoId] = useState<string | undefined>(undefined)

  const loadDashboard = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, requests, roles, employees] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listVisitRequestsUseCase.execute(scope === 'mine'),
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
        setVisitRequests(requests)
        setRoles(roles)
        setRoleNameById(Object.fromEntries(roles.map((role: RoleOut) => [role.id, role.name])))
        setHostEmployees(employees)
        setEmployeeNameById(Object.fromEntries(employees.map((employee) => [employee.id, employee.fullName])))
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
    [getCurrentStaffUserUseCase, listVisitRequestsUseCase, listRolesUseCase, listHostEmployeesUseCase, scope, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate(loginRedirectPath, { replace: true })
      return
    }

    void loadDashboard()
  }, [navigate, loginRedirectPath, loadDashboard])

  const refresh = useCallback(() => {
    void loadDashboard()
  }, [loadDashboard])

  // Tracks whether a deny/reschedule/delegate action or its dialog is in
  // progress, so the auto-refresh tick below can skip a fetch that would
  // otherwise disrupt it.
  const actionInProgressRef = useRef(false)
  useEffect(() => {
    actionInProgressRef.current =
      pendingDenyId !== undefined ||
      pendingRescheduleId !== undefined ||
      pendingDelegateId !== undefined ||
      pendingEditId !== undefined ||
      pendingApproveAndDelegateId !== undefined ||
      denyingId !== undefined ||
      reschedulingId !== undefined ||
      delegatingId !== undefined ||
      editingId !== undefined ||
      approvingAndDelegatingId !== undefined
  }, [
    pendingDenyId,
    pendingRescheduleId,
    pendingDelegateId,
    pendingEditId,
    pendingApproveAndDelegateId,
    denyingId,
    reschedulingId,
    delegatingId,
    editingId,
    approvingAndDelegatingId,
  ])

  useEffect(() => {
    const intervalId = setInterval(() => {
      if (actionInProgressRef.current) return
      void loadDashboard({ silent: true })
    }, 30_000)

    return () => clearInterval(intervalId)
  }, [loadDashboard])

  // Preloads approval-step detail for pending requests so the "Level X/Y"
  // badge is visible on the collapsed card, not just after expanding it.
  // Also covers "approved" requests: the backend's `status` field flips to
  // "approved" as soon as an intermediate step (e.g. Reception) clears, even
  // when a further step is still pending, so a genuinely mid-workflow request
  // needs its detail fetched here too for `resolveEffectiveStatus` below to
  // correctly keep it out of the Approved column.
  const pendingDetailFetchesRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    const idsNeedingDetail = visitRequests
      .filter((request) => ['requested', 'approved'].includes(normalizeStatus(request.status)))
      .map((request) => request.id)
      .filter((id) => !invitationDetails[id] && !pendingDetailFetchesRef.current.has(id))

    idsNeedingDetail.forEach((id) => {
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
    })
  }, [visitRequests, invitationDetails, getInvitationDetailUseCase])

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
        .execute(visitorCategoryId)
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

      setLoadingDetailId(id)
      try {
        const detail = await getInvitationDetailUseCase.execute(id)
        setInvitationDetails((previous) => ({ ...previous, [id]: detail }))
        return detail
      } finally {
        setLoadingDetailId(undefined)
      }
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

  const toggleExpand = useCallback(
    (id: string) => {
      if (expandedId === id) {
        setExpandedId(undefined)
        return
      }

      setExpandedId(id)
      void loadDetail(id).catch((error: unknown) => {
        console.error('Failed to load invitation detail', error)
        toast.error('Could not load approval progress for this request.')
      })
    },
    [expandedId, loadDetail, toast],
  )

  // Opens the invitation named by ?invitationId=... (e.g. from a clicked push
  // notification) the same way clicking its card does, once on mount.
  const hasOpenedDeepLinkRef = useRef(false)
  useEffect(() => {
    if (hasOpenedDeepLinkRef.current) return
    const invitationId = searchParams.get('invitationId')
    if (!invitationId) return

    hasOpenedDeepLinkRef.current = true
    setExpandedId(invitationId)
    void loadDetail(invitationId).catch((error: unknown) => {
      console.error('Failed to load invitation detail from notification link', error)
      toast.error('Could not load approval progress for this request.')
    })
  }, [searchParams, loadDetail, toast])

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

        await loadDashboard()
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

  const reschedule = useCallback(
    async (id: string, preferredVisitDate: string, preferredVisitTime: string) => {
      setReschedulingId(id)

      try {
        await rescheduleInvitationUseCase.execute(id, preferredVisitDate, preferredVisitTime)
        setPendingRescheduleId(undefined)
        toast.success('Visit request rescheduled.')
        await loadDashboard()
      } catch (error) {
        console.error('Failed to reschedule visit request', error)
        toast.error(error instanceof Error ? error.message : 'Failed to reschedule the visit request. Please try again.')
      } finally {
        setReschedulingId(undefined)
      }
    },
    [rescheduleInvitationUseCase, loadDashboard, toast],
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

        await loadDashboard()
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
        const rules = await ensureWorkflowRulesLoaded(detail.visitorCategoryId)
        const sortedRules = [...rules].sort((a, b) => a.stepOrder - b.stepOrder)
        const currentIndex = step.approverRoleId ? sortedRules.findIndex((rule) => rule.approverRoleId === step.approverRoleId) : -1
        const nextRule = currentIndex !== -1 ? sortedRules[currentIndex + 1] : undefined
        const nextRoleName = nextRule ? roleNameById[nextRule.approverRoleId] : undefined
        if (!nextRoleName) return

        setNextStepCandidates(hostEmployees.filter((employee) => employeeHasRoleAtBranch(employee, nextRoleName, detail.branchId)))
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
        await loadDashboard()
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
        await loadDashboard()
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
        await loadDashboard()
      } catch (error) {
        console.error('Failed to deny visit request', error)
        toast.error(error instanceof Error ? error.message : 'Failed to deny the visit request. Please try again.')
      } finally {
        setDenyingId(undefined)
      }
    },
    [pendingDenyId, denyInvitationUseCase, rejectInvitationStepUseCase, loadDashboard, loadDetail, workflowRulesByCategory, toast],
  )

  const purposeOptions = useMemo(
    () => [{ value: 'all', label: 'All purposes' }, ...PURPOSE_OF_VISIT_OPTIONS],
    [],
  )

  const filteredRequests = useMemo(() => {
    const query = search.trim().toLowerCase()

    return visitRequests.filter((request) => {
      const matchesSearch =
        !query ||
        request.primaryContactFullName.toLowerCase().includes(query) ||
        request.trackingId.toLowerCase().includes(query)
      const matchesPurpose = purposeFilter === 'all' || request.purposeOfVisit === purposeFilter
      const matchesRegistrationType = registrationTypeFilter === 'all' || request.registrationType === registrationTypeFilter

      return matchesSearch && matchesPurpose && matchesRegistrationType
    })
  }, [visitRequests, search, purposeFilter, registrationTypeFilter])

  // The backend's `status` field on a visit request flips to "approved" as
  // soon as any single step clears (e.g. Reception approves-and-delegates),
  // even though a further step is still pending — it doesn't track
  // multi-step completion itself. Once this invitation's detail has been
  // fetched, `currentApprovalStep` is the real source of truth: a step still
  // pending means the request hasn't actually finished the workflow, so keep
  // it in "Requested" until that step clears too (`currentApprovalStep` null).
  const resolveEffectiveStatus = useCallback(
    (request: VisitRequestSummary): string => {
      const status = normalizeStatus(request.status)
      if (status === 'approved' && invitationDetails[request.id]?.currentApprovalStep) {
        return 'requested'
      }
      return status
    },
    [invitationDetails],
  )

  const columns = useMemo(
    () =>
      BOARD_STATUS_COLUMNS.map((column) => ({
        ...column,
        requests: filteredRequests.filter((request) => resolveEffectiveStatus(request) === column.status),
      })),
    [filteredRequests, resolveEffectiveStatus],
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
    refresh,
    approve,
    approvingId,
    expandedId,
    toggleExpand,
    invitationDetails,
    loadingDetailId,
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
