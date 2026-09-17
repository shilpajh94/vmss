import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import type { SecurityGate } from '../../../../domain/entities/security-gate-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const PAGE_SIZE = 20

export function useAdminSecurityGates() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listSecurityGatesPageUseCase, listBuildingsUseCase, deleteSecurityGateUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [securityGates, setSecurityGates] = useState<SecurityGate[]>([])
  const [total, setTotal] = useState(0)
  const [buildingOptions, setBuildingOptions] = useState<{ value: string; label: string }[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<SecurityGate | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [buildingFilter, setBuildingFilter] = useState('')
  const [gateTypeFilter, setGateTypeFilter] = useState('')
  const [securityLevelFilter, setSecurityLevelFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  const loadSecurityGates = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, page_, buildings] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listSecurityGatesPageUseCase.execute({
            page,
            pageSize: PAGE_SIZE,
            buildingId: buildingFilter || undefined,
            gateType: gateTypeFilter === 'entry' || gateTypeFilter === 'exit' || gateTypeFilter === 'both' ? gateTypeFilter : undefined,
            securityLevel: securityLevelFilter === 'standard' || securityLevelFilter === 'high' ? securityLevelFilter : undefined,
          }),
          listBuildingsUseCase.execute(),
        ])
        setCurrentUser(user)
        setSecurityGates(page_.items)
        setTotal(page_.total)
        setBuildingOptions(buildings.map((building) => ({ value: building.id, label: building.name })).sort((a, b) => a.label.localeCompare(b.label)))
        setLastUpdatedAt(new Date())
      } catch {
        if (!silent) {
          setErrorMessage('Something went wrong loading the security gates. Please try again.')
        }
        toast.error('Something went wrong loading the security gates. Please try again.')
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [
      getCurrentStaffUserUseCase,
      listSecurityGatesPageUseCase,
      listBuildingsUseCase,
      page,
      buildingFilter,
      gateTypeFilter,
      securityLevelFilter,
      toast,
    ],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadSecurityGates()
  }, [navigate, loadSecurityGates])

  const retry = useCallback(() => {
    void loadSecurityGates()
  }, [loadSecurityGates])

  // Auto-refreshes the register every 15s; skipped while a delete dialog is
  // open so a background tick can't replace data underneath it.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  usePolling(() => void loadSecurityGates({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: isLoading, lastUpdatedAt })

  const isFiltering = buildingFilter !== '' || gateTypeFilter !== '' || securityLevelFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  const changeBuildingFilter = useCallback(
    (value: string) => {
      setBuildingFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeGateTypeFilter = useCallback(
    (value: string) => {
      setGateTypeFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeSecurityLevelFilter = useCallback(
    (value: string) => {
      setSecurityLevelFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const clearFilters = useCallback(() => {
    setBuildingFilter('')
    setGateTypeFilter('')
    setSecurityLevelFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

  const requestDelete = useCallback((securityGate: SecurityGate) => {
    setPendingDelete(securityGate)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteSecurityGateUseCase.execute(pendingDelete.id)
      toast.success('Security gate deleted.')
      setPendingDelete(undefined)
      await loadSecurityGates({ silent: true })
    } catch {
      toast.error('Something went wrong deleting the security gate. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteSecurityGateUseCase, toast, loadSecurityGates])

  return {
    currentUser,
    securityGates,
    total,
    page,
    pageSize: PAGE_SIZE,
    goToNextPage,
    goToPrevPage,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    buildingOptions,
    buildingFilter,
    setBuildingFilter: changeBuildingFilter,
    gateTypeFilter,
    setGateTypeFilter: changeGateTypeFilter,
    securityLevelFilter,
    setSecurityLevelFilter: changeSecurityLevelFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
