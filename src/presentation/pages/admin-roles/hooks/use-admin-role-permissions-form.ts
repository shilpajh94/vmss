import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { RoleOut } from '../../../../domain/entities/role-out-schema'
import type { PermissionOut } from '../../../../domain/entities/permission-out-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'

export function useAdminRolePermissionsForm() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const { getCurrentStaffUserUseCase, listRolesUseCase, listPermissionsUseCase, updateRolePermissionsUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [role, setRole] = useState<RoleOut | undefined>(undefined)
  const [permissions, setPermissions] = useState<PermissionOut[]>([])
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, roles, permissionCatalog] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listRolesUseCase.execute(),
        listPermissionsUseCase.execute(),
      ])
      setCurrentUser(user)
      setPermissions(permissionCatalog)

      const found = roles.find((candidate) => candidate.id === id)
      if (!found) {
        setErrorMessage('That role could not be found.')
        return
      }
      setRole(found)
      setSelectedCodes(new Set(found.permissionCodes))
    } catch (error) {
      console.error('Failed to load role permissions', error)
      setErrorMessage('Something went wrong loading this role. Please try again.')
      toast.error('Something went wrong loading this role. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listRolesUseCase, listPermissionsUseCase, id, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void load()
  }, [navigate, load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  useFormPageRefresh({ values: { permissionCodes: [...selectedCodes].sort() }, isLoading, reload: retry })

  const togglePermission = useCallback((code: string, checked: boolean) => {
    setSelectedCodes((current) => {
      const next = new Set(current)
      if (checked) {
        next.add(code)
      } else {
        next.delete(code)
      }
      return next
    })
  }, [])

  const submit = useCallback(async () => {
    if (!role) return

    setIsSaving(true)
    try {
      await updateRolePermissionsUseCase.execute(role.id, Array.from(selectedCodes))
      toast.success('Role permissions updated.')
      navigate('/admin/roles')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Something went wrong updating this role. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }, [role, selectedCodes, updateRolePermissionsUseCase, navigate, toast])

  const cancel = useCallback(() => {
    navigate('/admin/roles')
  }, [navigate])

  return {
    currentUser,
    role,
    permissions,
    selectedCodes,
    isLoading,
    errorMessage,
    retry,
    isSaving,
    togglePermission,
    submit,
    cancel,
  }
}
