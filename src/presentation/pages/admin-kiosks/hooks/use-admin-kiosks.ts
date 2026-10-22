import { useCallback, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import { ApiError } from '../../../../data/api/api-error'
import type { Kiosk } from '../../../../domain/entities/kiosk-schema'
import { canManageKiosks } from '../can-manage-kiosks'

const PAGE_SIZE = 20
const EMPTY_KIOSKS: Kiosk[] = []

function loadErrorText(error: unknown): string {
  return error instanceof ApiError && error.status === 403
    ? 'You do not have permission to view kiosks.'
    : 'Something went wrong loading the kiosks. Please try again.'
}

export type KioskSort = 'name:asc' | 'name:desc' | 'created_at:asc' | 'created_at:desc'

export function useAdminKiosks() {
  const {
    listKiosksPageUseCase,
    updateKioskUseCase,
    setKioskVisibilityUseCase,
    deleteKioskUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()

  const [pendingDelete, setPendingDelete] = useState<Kiosk | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)
  const [busyKioskId, setBusyKioskId] = useState<string | undefined>(undefined)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [showHidden, setShowHiddenState] = useState(false)
  const [sort, setSortState] = useState<KioskSort>('name:asc')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  const canManage = canManageKiosks(currentUser)

  const isActionInProgress = pendingDelete !== undefined || isDeleting || busyKioskId !== undefined
  const resource = useLiveResource({
    load: () => {
      const [sortBy, sortOrder] = sort.split(':') as ['name' | 'created_at', 'asc' | 'desc']
      return listKiosksPageUseCase.execute({
        page,
        pageSize: PAGE_SIZE,
        status: statusFilter === 'active' || statusFilter === 'inactive' ? statusFilter : undefined,
        includeHidden: showHidden,
        sortBy,
        sortOrder,
      })
    },
    query: { page, statusFilter, showHidden, sort },
    errorMessage: loadErrorText,
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, reload } = resource
  const kiosks = resource.data?.items ?? EMPTY_KIOSKS
  const total = resource.data?.total ?? 0
  // Only shown when the first load fails; keeps the 403 vs generic wording.
  const loadErrorMessage = phase === 'error' ? loadErrorText(resource.error) : undefined

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
        void reload()
      } else if (error instanceof ApiError && (error.status === 403 || error.status === 409 || error.status === 422)) {
        toast.error(error.message)
      } else {
        toast.error(fallback)
      }
    },
    [toast, reload],
  )

  const toggleActive = useCallback(
    async (kiosk: Kiosk) => {
      setBusyKioskId(kiosk.id)
      try {
        await updateKioskUseCase.execute(kiosk.id, { isActive: !kiosk.isActive })
        await reload()
      } catch (error) {
        reportMutationError(error, 'Something went wrong updating the kiosk. Please try again.')
      } finally {
        setBusyKioskId(undefined)
      }
    },
    [updateKioskUseCase, reload, reportMutationError],
  )

  const toggleHidden = useCallback(
    async (kiosk: Kiosk) => {
      setBusyKioskId(kiosk.id)
      try {
        await setKioskVisibilityUseCase.execute(kiosk.id, !kiosk.isHidden)
        toast.success(kiosk.isHidden ? 'Kiosk unhidden.' : 'Kiosk hidden.')
        await reload()
      } catch (error) {
        reportMutationError(error, 'Something went wrong updating the kiosk. Please try again.')
      } finally {
        setBusyKioskId(undefined)
      }
    },
    [setKioskVisibilityUseCase, toast, reload, reportMutationError],
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
      await reload()
    } catch (error) {
      setPendingDelete(undefined)
      reportMutationError(error, 'Something went wrong deleting the kiosk. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteKioskUseCase, toast, reload, reportMutationError])

  return {
    canManage,
    kiosks,
    total,
    page,
    pageSize: PAGE_SIZE,
    goToNextPage,
    goToPrevPage,
    phase,
    isRefreshing,
    loadErrorMessage,
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
