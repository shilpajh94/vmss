import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { HostEmployee } from '../../../../domain/entities/host-employee-schema'

export type BranchFormState = { mode: 'edit'; branch: Branch } | undefined

export function useAdminBranches() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listBranchesUseCase, listHostEmployeesUseCase, updateBranchUseCase, deleteBranchUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [branches, setBranches] = useState<Branch[]>([])
  const [employees, setEmployees] = useState<HostEmployee[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [formState, setFormState] = useState<BranchFormState>(undefined)
  const [isSaving, setIsSaving] = useState(false)

  const [pendingDelete, setPendingDelete] = useState<Branch | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')

  const loadBranches = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, list, employeeList] = await Promise.all([
        getCurrentStaffUserUseCase.execute(),
        listBranchesUseCase.execute(),
        listHostEmployeesUseCase.execute(),
      ])
      setCurrentUser(user)
      setBranches(list)
      setEmployees(employeeList)
    } catch {
      setErrorMessage('Something went wrong loading the branches. Please try again.')
      toast.error('Something went wrong loading the branches. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listBranchesUseCase, listHostEmployeesUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadBranches()
  }, [navigate, loadBranches])

  const retry = useCallback(() => {
    void loadBranches()
  }, [loadBranches])

  const openEditForm = useCallback((branch: Branch) => {
    setFormState({ mode: 'edit', branch })
  }, [])

  const closeForm = useCallback(() => {
    setFormState(undefined)
  }, [])

  const saveBranch = useCallback(
    async (input: Omit<Branch, 'id'>) => {
      if (!formState) return

      setIsSaving(true)
      try {
        const updated = await updateBranchUseCase.execute(formState.branch.id, input)
        setBranches((current) => current.map((branch) => (branch.id === updated.id ? updated : branch)))
        toast.success('Branch updated.')
        setFormState(undefined)
      } catch {
        toast.error('Something went wrong saving the branch. Please try again.')
      } finally {
        setIsSaving(false)
      }
    },
    [formState, updateBranchUseCase, toast],
  )

  const requestDelete = useCallback((branch: Branch) => {
    setPendingDelete(branch)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteBranchUseCase.execute(pendingDelete.id)
      setBranches((current) => current.filter((branch) => branch.id !== pendingDelete.id))
      toast.success('Branch deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the branch. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteBranchUseCase, toast])

  const filteredBranches = useMemo(() => {
    return branches.filter((branch) => {
      if (statusFilter && (statusFilter === 'active') !== branch.isActive) return false
      return true
    })
  }, [branches, statusFilter])

  const isFiltering = statusFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])
  const clearFilters = useCallback(() => setStatusFilter(''), [])

  return {
    currentUser,
    branches: filteredBranches,
    hasAnyBranches: branches.length > 0,
    employees,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    statusFilter,
    setStatusFilter,
    clearFilters,
    isFiltering,
    formState,
    isSaving,
    openEditForm,
    closeForm,
    saveBranch,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
