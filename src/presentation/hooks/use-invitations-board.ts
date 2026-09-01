import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../context/app-dependencies-context'
import { useToast } from '../components/toast/toast-context'
import type { VisitRequestSummary } from '../../domain/entities/visit-request-summary-schema'
import type { StaffUser } from '../../domain/entities/staff-user-schema'
import type { InvitationDetail } from '../../domain/entities/invitation-detail-schema'
import type { RoleOut } from '../../domain/entities/role-out-schema'

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

// Shared Kanban-board data/actions behind the staff dashboard and the admin
// invitations board — same columns, same approve/reschedule/step-progress
// behavior, differing only in where an unauthenticated visitor is redirected.
export function useInvitationsBoard(loginRedirectPath: string) {
  const navigate = useNavigate()
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
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [visitRequests, setVisitRequests] = useState<VisitRequestSummary[]>([])
  const [roleNameById, setRoleNameById] = useState<Record<string, string>>({})
  const [employeeNameById, setEmployeeNameById] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [search, setSearch] = useState('')
  const [approvingId, setApprovingId] = useState<string | undefined>(undefined)
  const [expandedId, setExpandedId] = useState<string | undefined>(undefined)
  const [invitationDetails, setInvitationDetails] = useState<Record<string, InvitationDetail>>({})
  const [loadingDetailId, setLoadingDetailId] = useState<string | undefined>(undefined)
  const [reschedulingId, setReschedulingId] = useState<string | undefined>(undefined)
  const [pendingDenyId, setPendingDenyId] = useState<string | undefined>(undefined)
  const [denyingId, setDenyingId] = useState<string | undefined>(undefined)

  const loadDashboard = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, requests, roles, employees] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listVisitRequestsUseCase.execute(),
        listRolesUseCase.execute(),
        listHostEmployeesUseCase.execute(),
      ])
      setCurrentUser(user)
      setVisitRequests(requests)
      setRoleNameById(Object.fromEntries(roles.map((role: RoleOut) => [role.id, role.name])))
      setEmployeeNameById(Object.fromEntries(employees.map((employee) => [employee.id, employee.fullName])))
    } catch (error) {
      console.error('Failed to load dashboard', error)
      setErrorMessage('Something went wrong loading the dashboard. Please try again.')
      toast.error('Something went wrong loading the dashboard. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listVisitRequestsUseCase, listRolesUseCase, listHostEmployeesUseCase, toast])

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

  const approve = useCallback(
    async (id: string) => {
      setApprovingId(id)

      try {
        const detail = await loadDetail(id)

        if (detail.currentApprovalStep) {
          await approveInvitationStepUseCase.execute(id, detail.currentApprovalStep.id)
        } else {
          await approveInvitationUseCase.execute(id)
        }

        toast.success('Visit request approved.')
        await loadDashboard()
      } catch (error) {
        console.error('Failed to approve visit request', error)
        toast.error(error instanceof Error ? error.message : 'Failed to approve the visit request. Please try again.')
      } finally {
        setApprovingId(undefined)
      }
    },
    [approveInvitationUseCase, approveInvitationStepUseCase, loadDashboard, loadDetail, toast],
  )

  const reschedule = useCallback(
    async (id: string, preferredVisitDate: string, preferredVisitTime: string) => {
      setReschedulingId(id)

      try {
        await rescheduleInvitationUseCase.execute(id, preferredVisitDate, preferredVisitTime)
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
        } else {
          await denyInvitationUseCase.execute(id, reason)
        }

        toast.success('Visit request denied.')
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

  const filteredRequests = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return visitRequests

    return visitRequests.filter(
      (request) =>
        request.primaryContactFullName.toLowerCase().includes(query) ||
        request.trackingId.toLowerCase().includes(query),
    )
  }, [visitRequests, search])

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
    refresh,
    approve,
    approvingId,
    expandedId,
    toggleExpand,
    invitationDetails,
    loadingDetailId,
    roleNameById,
    employeeNameById,
    reschedule,
    reschedulingId,
    pendingDenyId,
    requestDeny,
    cancelDeny,
    confirmDeny,
    denyingId,
  }
}
