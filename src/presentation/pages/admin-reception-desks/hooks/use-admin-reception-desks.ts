import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import type { ReceptionDesk } from '../../../../domain/entities/reception-desk-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export function useAdminReceptionDesks() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listReceptionDesksUseCase, deleteReceptionDeskUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [receptionDesks, setReceptionDesks] = useState<ReceptionDesk[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<ReceptionDesk | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [buildingFilter, setBuildingFilter] = useState('')
  const [floorFilter, setFloorFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const loadReceptionDesks = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, list] = await Promise.all([getCurrentStaffUserUseCase.execute(), listReceptionDesksUseCase.execute()])
        setCurrentUser(user)
        setReceptionDesks(list)
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
    [getCurrentStaffUserUseCase, listReceptionDesksUseCase, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadReceptionDesks()
  }, [navigate, loadReceptionDesks])

  const retry = useCallback(() => {
    void loadReceptionDesks()
  }, [loadReceptionDesks])

  // Auto-refreshes the register every 15s; skipped while a delete dialog is
  // open so a background tick can't replace data underneath it.
  const isActionInProgress = pendingDelete !== undefined || isDeleting
  usePolling(() => void loadReceptionDesks({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

  const buildingOptions = useMemo(() => {
    const seen = new Map<string, string>()
    for (const desk of receptionDesks) {
      if (!seen.has(desk.buildingId)) seen.set(desk.buildingId, desk.buildingName)
    }
    return [...seen.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label))
  }, [receptionDesks])

  const floorOptions = useMemo(() => {
    const seen = new Map<string, string>()
    for (const desk of receptionDesks) {
      if (!seen.has(desk.floorId)) seen.set(desk.floorId, desk.floorName ?? desk.floorId)
    }
    return [...seen.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label))
  }, [receptionDesks])

  const filteredReceptionDesks = useMemo(() => {
    return receptionDesks.filter((desk) => {
      if (buildingFilter && desk.buildingId !== buildingFilter) return false
      if (floorFilter && desk.floorId !== floorFilter) return false
      if (statusFilter && desk.status !== statusFilter) return false
      return true
    })
  }, [receptionDesks, buildingFilter, floorFilter, statusFilter])

  const isFiltering = buildingFilter !== '' || floorFilter !== '' || statusFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])
  const clearFilters = useCallback(() => {
    setBuildingFilter('')
    setFloorFilter('')
    setStatusFilter('')
  }, [])

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
      setReceptionDesks((current) => current.filter((receptionDesk) => receptionDesk.id !== pendingDelete.id))
      toast.success('Reception desk deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the reception desk. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteReceptionDeskUseCase, toast])

  return {
    currentUser,
    receptionDesks: filteredReceptionDesks,
    hasAnyReceptionDesks: receptionDesks.length > 0,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    buildingOptions,
    buildingFilter,
    setBuildingFilter,
    floorOptions,
    floorFilter,
    setFloorFilter,
    statusFilter,
    setStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
