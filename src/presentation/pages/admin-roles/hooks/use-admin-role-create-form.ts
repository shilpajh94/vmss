import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import type { PermissionOut } from '../../../../domain/entities/permission-out-schema'
import { useFormPageRefresh } from '../../../hooks/use-form-page-refresh'
import { toUserMessage } from '../../../utils/to-user-message'

export function useAdminRoleCreateForm() {
  const navigate = useNavigate()
  const { listPermissionsUseCase, createRoleUseCase } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()
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
      const permissionCatalog = await listPermissionsUseCase.execute()
      setPermissions(permissionCatalog)
    } catch (error) {
      console.error('Failed to load permission catalog', error)
      setErrorMessage('Something went wrong loading the permission catalog. Please try again.')
      toast.error('Something went wrong loading the permission catalog. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [listPermissionsUseCase, toast])

  useEffect(() => {
    void load()
  }, [load])

  const retry = useCallback(() => {
    void load()
  }, [load])

  // A confirmed top-bar refresh starts the role over: load() itself leaves
  // the typed name, description and picked permissions alone.
  const reload = useCallback(() => {
    setName('')
    setDescription('')
    setSelectedCodes(new Set())
    setNameError(undefined)
    void load()
  }, [load])

  const { release } = useFormPageRefresh({ values: { name, description, permissionCodes: [...selectedCodes].sort() }, isLoading, reload })

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
      release()
      navigate('/admin/roles')
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong creating this role. Please try again.'))
    } finally {
      setIsSaving(false)
    }
  }, [name, description, selectedCodes, createRoleUseCase, navigate, toast, release])

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
