import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import type { ReceptionDesk } from '../../../../domain/entities/reception-desk-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

const PAGE_SIZE = 20

export function useAdminReceptionDesks() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listReceptionDesksPageUseCase, listBuildingsUseCase, listFloorsUseCase, deleteReceptionDeskUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [receptionDesks, setReceptionDesks] = useState<ReceptionDesk[]>([])
  const [total, setTotal] = useState(0)
  const [buildingOptions, setBuildingOptions] = useState<{ value: string; label: string }[]>([])
  const [floorOptions, setFloorOptions] = useState<{ value: string; label: string }[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<ReceptionDesk | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  // Building only narrows the Floor field's own options - it's never sent to
  // the server, since a reception desk has no buildingId on the API (only
  // floorId). See the admin-reception-desks spec delta. Kept out of
  // loadReceptionDesks's dependencies so selecting a Building doesn't
  // re-fetch the desks list by itself.
  const [buildingFilter, setBuildingFilter] = useState('')
  const [floorFilter, setFloorFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  const loadReceptionDesks = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, page_, buildings] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listReceptionDesksPageUseCase.execute({
            page,
            pageSize: PAGE_SIZE,
            floorId: floorFilter || undefined,
            status: statusFilter === 'active' || statusFilter === 'maintenance' || statusFilter === 'inactive' ? statusFilter : undefined,
          }),
          listBuildingsUseCase.execute(),
        ])
        setCurrentUser(user)
        setReceptionDesks(page_.items)
        setTotal(page_.total)
        setBuildingOptions(buildings.map((building) => ({ value: building.id, label: building.name })).sort((a, b) => a.label.localeCompare(b.label)))
        setLastUpdatedAt(new Date())
      } catch {
        if (!silent) {
          setErrorMessage('Something went wrong loading the reception desks. Please try again.')
        }
        toast.error('Something went wrong loading the reception desks. Please try again.')
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [getCurrentStaffUserUseCase, listReceptionDesksPageUseCase, listBuildingsUseCase, page, floorFilter, statusFilter, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadReceptionDesks()
  }, [navigate, loadReceptionDesks])

  // Floor dropdown options cascade off the selected Building, independent of
  // the desks list fetch above - selecting a Building never re-fetches desks.
  useEffect(() => {
    if (!sessionStorage.getItem('token')) return
    listFloorsUseCase
      .execute(buildingFilter || undefined)
      .then((floors) => setFloorOptions(floors.map((floor) => ({ value: floor.id, label: floor.name })).sort((a, b) => a.label.localeCompare(b.label))))
      .catch(() => {
        // The Floor field simply shows no options if this fails; the rest of the page still works.
      })
  }, [listFloorsUseCase, buildingFilter])

  const retry = useCallback(() => {
    void loadReceptionDesks()
  }, [loadReceptionDesks])

  // Auto-refreshes the register every 15s; skipped while a delete dialog is
  // open so a background tick can't replace data underneath it.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  usePolling(() => void loadReceptionDesks({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: isLoading, lastUpdatedAt })

  const isFiltering = buildingFilter !== '' || floorFilter !== '' || statusFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  // Selecting a Building only re-narrows the Floor options - no request, no
  // page reset, since Building is never sent to the server by itself.
  const changeBuildingFilter = useCallback((value: string) => {
    setBuildingFilter(value)
    setFloorFilter('')
  }, [])

  const changeFloorFilter = useCallback(
    (value: string) => {
      setFloorFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const changeStatusFilter = useCallback(
    (value: string) => {
      setStatusFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )

  const clearFilters = useCallback(() => {
    setBuildingFilter('')
    setFloorFilter('')
    setStatusFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

  const requestDelete = useCallback((receptionDesk: ReceptionDesk) => {
    setPendingDelete(receptionDesk)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteReceptionDeskUseCase.execute(pendingDelete.id)
      toast.success('Reception desk deleted.')
      setPendingDelete(undefined)
      await loadReceptionDesks({ silent: true })
    } catch {
      toast.error('Something went wrong deleting the reception desk. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteReceptionDeskUseCase, toast, loadReceptionDesks])

  return {
    currentUser,
    receptionDesks,
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
    floorOptions,
    floorFilter,
    setFloorFilter: changeFloorFilter,
    statusFilter,
    setStatusFilter: changeStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
