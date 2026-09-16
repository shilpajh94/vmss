import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
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
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [isResyncing, setIsResyncing] = useState(false)
  const [resyncResult, setResyncResult] = useState<RolePermissionResyncEntry[] | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const { page, goToNextPage, goToPrevPage } = usePagedList()

  const loadRoles = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, page_] = await Promise.all([getCurrentStaffUserUseCase.execute(), listRolesPageUseCase.execute({ page, pageSize: PAGE_SIZE })])
        setCurrentUser(user)
        setRoles(page_.items)
        setTotal(page_.total)
        setLastUpdatedAt(new Date())
      } catch {
        if (!silent) {
          setErrorMessage('Something went wrong loading the roles. Please try again.')
        }
        toast.error('Something went wrong loading the roles. Please try again.')
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [getCurrentStaffUserUseCase, listRolesPageUseCase, page, toast],
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
  usePolling(() => void loadRoles({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: isLoading, lastUpdatedAt })

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
    isLoading,
    errorMessage,
    retry,
    isResyncing,
    resyncResult,
    resyncPermissions,
  }
}
