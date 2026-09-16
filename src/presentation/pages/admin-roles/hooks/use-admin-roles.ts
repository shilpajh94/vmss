import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import type { RoleOut } from '../../../../domain/entities/role-out-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { RolePermissionResyncEntry } from '../../../../domain/entities/permission-out-schema'

export function useAdminRoles() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listRolesUseCase, resyncRolePermissionsUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [roles, setRoles] = useState<RoleOut[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [isResyncing, setIsResyncing] = useState(false)
  const [resyncResult, setResyncResult] = useState<RolePermissionResyncEntry[] | undefined>(undefined)

  const loadRoles = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, roleList] = await Promise.all([getCurrentStaffUserUseCase.execute(), listRolesUseCase.execute()])
        setCurrentUser(user)
        setRoles(roleList)
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
    [getCurrentStaffUserUseCase, listRolesUseCase, toast],
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
    isLoading,
    errorMessage,
    retry,
    isResyncing,
    resyncResult,
    resyncPermissions,
  }
}
