import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { RoleOut } from '../../../../domain/entities/role-out-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { RolePermissionResyncEntry } from '../../../../domain/entities/permission-out-schema'

const PAGE_SIZE = 20

export function useAdminRoles() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listRolesPageUseCase, resyncRolePermissionsUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [roles, setRoles] = useState<RoleOut[]>([])
  const [total, setTotal] = useState(0)
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [isResyncing, setIsResyncing] = useState(false)
  const [resyncResult, setResyncResult] = useState<RolePermissionResyncEntry[] | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const { page, goToNextPage, goToPrevPage } = usePagedList()

  // `user` (default): page/retry/refresh/post-resync - keeps the current
  // rows on screen with a progress cue. `background`: the 15s poll.
  const loadRoles = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, page_] = await Promise.all([getCurrentStaffUserUseCase.execute(), listRolesPageUseCase.execute({ page, pageSize: PAGE_SIZE })])
        if (!request.succeed()) return
        setCurrentUser(user)
        setRoles(page_.items)
        setTotal(page_.total)
        setLastUpdatedAt(new Date())
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the roles. Please try again.')
      }
    },
    [begin, getCurrentStaffUserUseCase, listRolesPageUseCase, page, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadRoles()
  }, [navigate, loadRoles])

  const retry = useCallback(() => {
    void loadRoles()
  }, [loadRoles])

  const isActionInProgress = isResyncing
  usePolling(() => void loadRoles('background'), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing, lastUpdatedAt })

  const resyncPermissions = useCallback(async () => {
    setIsResyncing(true)
    setResyncResult(undefined)

    try {
      const result = await resyncRolePermissionsUseCase.execute()
      setResyncResult(result)
      const grantedCount = result.reduce((sum, entry) => sum + entry.grantedPermissionCodes.length, 0)
      toast.success(grantedCount > 0 ? `Granted ${grantedCount} missing permission(s).` : 'All roles already have every catalog permission.')
      await loadRoles()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Something went wrong resyncing permissions. Please try again.')
    } finally {
      setIsResyncing(false)
    }
  }, [resyncRolePermissionsUseCase, loadRoles, toast])

  return {
    currentUser,
    roles,
    total,
    page,
    pageSize: PAGE_SIZE,
    goToNextPage,
    goToPrevPage,
    phase,
    isRefreshing,
    retry,
    isResyncing,
    resyncResult,
    resyncPermissions,
  }
}
