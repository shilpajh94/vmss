import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { ApiError } from '../../../../data/api/api-error'
import type { Kiosk } from '../../../../domain/entities/kiosk-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { canManageKiosks } from '../can-manage-kiosks'

const PAGE_SIZE = 20

export type KioskSort = 'name:asc' | 'name:desc' | 'created_at:asc' | 'created_at:desc'

export function useAdminKiosks() {
  const navigate = useNavigate()
  const {
    getCurrentStaffUserUseCase,
    listKiosksPageUseCase,
    updateKioskUseCase,
    setKioskVisibilityUseCase,
    deleteKioskUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [kiosks, setKiosks] = useState<Kiosk[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<Kiosk | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)
  const [busyKioskId, setBusyKioskId] = useState<string | undefined>(undefined)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [showHidden, setShowHiddenState] = useState(false)
  const [sort, setSortState] = useState<KioskSort>('name:asc')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  const canManage = canManageKiosks(currentUser)

  const loadKiosks = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [sortBy, sortOrder] = sort.split(':') as ['name' | 'created_at', 'asc' | 'desc']
        const [user, kioskPage] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listKiosksPageUseCase.execute({
            page,
            pageSize: PAGE_SIZE,
            status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
            includeHidden: showHidden,
            sortBy,
            sortOrder,
          }),
        ])
        setCurrentUser(user)
        setKiosks(kioskPage.items)
        setTotal(kioskPage.total)
        setLastUpdatedAt(new Date())
      } catch (error) {
        const message =
          error instanceof ApiError && error.status === 403
            ? 'You do not have permission to view kiosks.'
            : 'Something went wrong loading the kiosks. Please try again.'
        if (!silent) setErrorMessage(message)
        toast.error(message)
      } finally {
        if (!silent) setIsLoading(false)
      }
    },
    [getCurrentStaffUserUseCase, listKiosksPageUseCase, page, statusFilter, showHidden, sort, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadKiosks()
  }, [navigate, loadKiosks])

  const retry = useCallback(() => {
    void loadKiosks()
  }, [loadKiosks])

  const isActionInProgress = pendingDelete !== undefined || isDeleting || busyKioskId !== undefined
  usePolling(() => void loadKiosks({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: isLoading, lastUpdatedAt })

  const isFiltering = statusFilter !== '' || showHidden
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  const changeStatusFilter = useCallback(
    (value: string) => {
      setStatusFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeShowHidden = useCallback(
    (value: boolean) => {
      setShowHiddenState(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeSort = useCallback(
    (value: string) => {
      setSortState(value as KioskSort)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const clearFilters = useCallback(() => {
    setStatusFilter('')
    setShowHiddenState(false)
    resetToFirstPage()
  }, [resetToFirstPage])

  // 404 means another admin deleted the kiosk; anything else is a generic failure.
  const reportMutationError = useCallback(
    (error: unknown, fallback: string) => {
      if (error instanceof ApiError && error.status === 404) {
        toast.error('That kiosk no longer exists.')
        void loadKiosks({ silent: true })
      } else if (error instanceof ApiError && (error.status === 403 || error.status === 409 || error.status === 422)) {
        toast.error(error.message)
      } else {
        toast.error(fallback)
      }
    },
    [toast, loadKiosks],
  )

  const toggleActive = useCallback(
    async (kiosk: Kiosk) => {
      setBusyKioskId(kiosk.id)
      try {
        await updateKioskUseCase.execute(kiosk.id, { isActive: !kiosk.isActive })
        await loadKiosks({ silent: true })
      } catch (error) {
        reportMutationError(error, 'Something went wrong updating the kiosk. Please try again.')
      } finally {
        setBusyKioskId(undefined)
      }
    },
    [updateKioskUseCase, loadKiosks, reportMutationError],
  )

  const toggleHidden = useCallback(
    async (kiosk: Kiosk) => {
      setBusyKioskId(kiosk.id)
      try {
        await setKioskVisibilityUseCase.execute(kiosk.id, !kiosk.isHidden)
        toast.success(kiosk.isHidden ? 'Kiosk unhidden.' : 'Kiosk hidden.')
        await loadKiosks({ silent: true })
      } catch (error) {
        reportMutationError(error, 'Something went wrong updating the kiosk. Please try again.')
      } finally {
        setBusyKioskId(undefined)
      }
    },
    [setKioskVisibilityUseCase, toast, loadKiosks, reportMutationError],
  )

  const requestDelete = useCallback((kiosk: Kiosk) => setPendingDelete(kiosk), [])
  const cancelDelete = useCallback(() => setPendingDelete(undefined), [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteKioskUseCase.execute(pendingDelete.id)
      toast.success('Kiosk deleted.')
      setPendingDelete(undefined)
      await loadKiosks({ silent: true })
    } catch (error) {
      setPendingDelete(undefined)
      reportMutationError(error, 'Something went wrong deleting the kiosk. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteKioskUseCase, toast, loadKiosks, reportMutationError])

  return {
    canManage,
    kiosks,
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
    statusFilter,
    setStatusFilter: changeStatusFilter,
    showHidden,
    setShowHidden: changeShowHidden,
    sort,
    setSort: changeSort,
    clearFilters,
    isFiltering,
    busyKioskId,
    toggleActive,
    toggleHidden,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
