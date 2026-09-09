import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { PermissionOut } from '../../../../domain/entities/permission-out-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export function useAdminRoleCreateForm() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listPermissionsUseCase, createRoleUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [permissions, setPermissions] = useState<PermissionOut[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [nameError, setNameError] = useState<string | undefined>(undefined)
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, permissionCatalog] = await Promise.all([getCurrentStaffUserUseCase.execute(), listPermissionsUseCase.execute()])
      setCurrentUser(user)
      setPermissions(permissionCatalog)
    } catch (error) {
      console.error('Failed to load permission catalog', error)
      setErrorMessage('Something went wrong loading the permission catalog. Please try again.')
      toast.error('Something went wrong loading the permission catalog. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listPermissionsUseCase, toast])

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
    const trimmedName = name.trim()
    if (!trimmedName) {
      setNameError('Role name is required.')
      return
    }
    setNameError(undefined)

    setIsSaving(true)
    try {
      await createRoleUseCase.execute({
        name: trimmedName,
        description: description.trim() || undefined,
        permissionCodes: Array.from(selectedCodes),
      })
      toast.success('Role created.')
      navigate('/admin/roles')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Something went wrong creating this role. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }, [name, description, selectedCodes, createRoleUseCase, navigate, toast])

  const cancel = useCallback(() => {
    navigate('/admin/roles')
  }, [navigate])

  return {
    currentUser,
    permissions,
    name,
    setName,
    description,
    setDescription,
    selectedCodes,
    isLoading,
    errorMessage,
    nameError,
    retry,
    isSaving,
    togglePermission,
    submit,
    cancel,
  }
}
