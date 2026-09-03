import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useAppDependencies } from '../context/app-dependencies-context'
import { useToast } from '../components/toast/toast-context'
import { resolveApproverLabel } from '../utils/approval-step-label'
import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'
import type { StaffUser } from '../../domain/entities/staff-user-schema'
import type { CurrentApprovalStep, InvitationDetail } from '../../domain/entities/invitation-detail-schema'
import type { RoleOut } from '../../domain/entities/role-out-schema'
import type { HostEmployee } from '../../domain/entities/host-employee-schema'
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
): string {
  if (!nextStep) {
    return `Level ${approvedStep.stepOrder} of ${approvedStep.totalSteps} approved — request fully approved.`
  }

  const approverLabel = resolveApproverLabel(nextStep, roleNameById, employeeNameById)
  return `Level ${approvedStep.stepOrder} of ${approvedStep.totalSteps} approved — now waiting on ${approverLabel} (level ${nextStep.stepOrder} of ${nextStep.totalSteps}).`
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
    denyInvitationUseCase,
    approveInvitationStepUseCase,
    rejectInvitationStepUseCase,
    delegateInvitationStepUseCase,
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
  const [pendingDenyId, setPendingDenyId] = useState<string | undefined>(undefined)
  const [denyingId, setDenyingId] = useState<string | undefined>(undefined)
  const [pendingRescheduleId, setPendingRescheduleId] = useState<string | undefined>(undefined)
  const [pendingDelegateId, setPendingDelegateId] = useState<string | undefined>(undefined)
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
          listRolesUseCase.execute(),
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
      denyingId !== undefined ||
      reschedulingId !== undefined ||
      delegatingId !== undefined
  }, [pendingDenyId, pendingRescheduleId, pendingDelegateId, denyingId, reschedulingId, delegatingId])

  useEffect(() => {
    const intervalId = setInterval(() => {
      if (actionInProgressRef.current) return
      void loadDashboard({ silent: true })
    }, 30_000)

    return () => clearInterval(intervalId)
  }, [loadDashboard])

  // Preloads approval-step detail for pending requests so the "Level X/Y"
  // badge is visible on the collapsed card, not just after expanding it.
  const pendingDetailFetchesRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    const idsNeedingDetail = visitRequests
      .filter((request) => normalizeStatus(request.status) === 'requested')
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

  const loadDetail = useCallback(
    async (id: string): Promise<InvitationDetail> => {
      if (invitationDetails[id]) return invitationDetails[id]

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
  // detail (GET /invitations/:id) the same way an approval-progress expand
  // does, so a repeat click reuses the cached detail instead of refetching.
  const viewVisitorInfo = useCallback(
    (id: string) => {
      setVisitorInfoId(id)
      void loadDetail(id).catch((error: unknown) => {
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
          await approveInvitationStepUseCase.execute(id, detail.currentApprovalStep.id)
          const updatedDetail = await getInvitationDetailUseCase.execute(id)
          setInvitationDetails((previous) => ({ ...previous, [id]: updatedDetail }))
          toast.success(
            describeApprovalOutcome(detail.currentApprovalStep, updatedDetail.currentApprovalStep, roleNameById, employeeNameById),
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

        await delegateInvitationStepUseCase.execute(id, detail.currentApprovalStep.id, delegateUserId)
        const updatedDetail = await getInvitationDetailUseCase.execute(id)
        setInvitationDetails((previous) => ({ ...previous, [id]: updatedDetail }))
        setPendingDelegateId(undefined)

        const approverLabel = employeeNameById[delegateUserId] ?? 'the selected host'
        toast.success(`Delegated level ${detail.currentApprovalStep.stepOrder} of ${detail.currentApprovalStep.totalSteps} to ${approverLabel}.`)

        await loadDashboard()
      } catch (error) {
        console.error('Failed to delegate approval step', error)
        toast.error(error instanceof Error ? error.message : 'Failed to delegate this approval step. Please try again.')
      } finally {
        setDelegatingId(undefined)
      }
    },
    [delegateInvitationStepUseCase, getInvitationDetailUseCase, loadDashboard, loadDetail, employeeNameById, toast],
  )

  const requestDelegate = useCallback((id: string) => {
    setPendingDelegateId(id)
  }, [])

  const cancelDelegate = useCallback(() => {
    setPendingDelegateId(undefined)
  }, [])

  const pendingDelegateDetail = pendingDelegateId ? invitationDetails[pendingDelegateId] : undefined

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
          toast.success(
            `Denied at level ${detail.currentApprovalStep.stepOrder} of ${detail.currentApprovalStep.totalSteps}.`,
          )
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
    [pendingDenyId, denyInvitationUseCase, rejectInvitationStepUseCase, loadDashboard, loadDetail, toast],
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

  const columns = useMemo(
    () =>
      BOARD_STATUS_COLUMNS.map((column) => ({
        ...column,
        requests: filteredRequests.filter((request) => normalizeStatus(request.status) === column.status),
      })),
    [filteredRequests],
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
    visitorInfoId,
    viewVisitorInfo,
    closeVisitorInfo,
  }
}
