import { useCallback, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import type { RoleOut } from '../../../../domain/entities/role-out-schema'
import type { RolePermissionResyncEntry } from '../../../../domain/entities/permission-out-schema'
import { toUserMessage } from '../../../utils/to-user-message'

const PAGE_SIZE = 20
const EMPTY_ROLES: RoleOut[] = []

export function useAdminRoles() {
  const { listRolesPageUseCase, resyncRolePermissionsUseCase } = useAppDependencies()
  const toast = useToast()
  const currentUser = useCurrentUser()

  const [isResyncing, setIsResyncing] = useState(false)
  const [resyncResult, setResyncResult] = useState<RolePermissionResyncEntry[] | undefined>(undefined)

  const { page, goToNextPage, goToPrevPage } = usePagedList()

  const resource = useLiveResource({
    load: () => listRolesPageUseCase.execute({ page, pageSize: PAGE_SIZE }),
    query: { page },
    errorMessage: 'Something went wrong loading the roles. Please try again.',
    isBusy: isResyncing,
  })
  const { phase, isRefreshing, retry, reload } = resource
  const roles = resource.data?.items ?? EMPTY_ROLES
  const total = resource.data?.total ?? 0

  const resyncPermissions = useCallback(async () => {
    setIsResyncing(true)
    setResyncResult(undefined)

    try {
      const result = await resyncRolePermissionsUseCase.execute()
      setResyncResult(result)
      const grantedCount = result.reduce((sum, entry) => sum + entry.grantedPermissionCodes.length, 0)
      toast.success(grantedCount > 0 ? `Granted ${grantedCount} missing permission(s).` : 'All roles already have every catalog permission.')
      await reload()
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong resyncing permissions. Please try again.'))
    } finally {
      setIsResyncing(false)
    }
  }, [resyncRolePermissionsUseCase, reload, toast])

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
