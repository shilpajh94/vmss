import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePolling } from '../../../hooks/use-polling'
import { usePagedList } from '../../../hooks/use-paged-list'
import { usePageRefresh } from '../../../context/refresh-context'
import { ApiError } from '../../../../data/api/api-error'
import type { Device, DeviceOperatingMode } from '../../../../domain/entities/managed-device-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { Building } from '../../../../domain/entities/building-schema'
import { canManageDevices } from '../can-manage-devices'
import { parseDeviceSort, statusFilterToQuery, type DeviceSort, type DeviceStatusFilter } from '../device-status-filter'

const PAGE_SIZE = 20

type DeviceAction = 'approve' | 'enable' | 'disable'

const ACTION_SUCCESS: Record<DeviceAction, string> = {
  approve: 'Device approved.',
  enable: 'Device enabled.',
  disable: 'Device disabled.',
}

export function useAdminDevices(operatingMode: DeviceOperatingMode, noun: string) {
  const navigate = useNavigate()
  const {
    getCurrentStaffUserUseCase,
    listDevicesPageUseCase,
    approveDeviceUseCase,
    enableDeviceUseCase,
    disableDeviceUseCase,
    deleteDeviceUseCase,
    listBranchesUseCase,
    listBuildingsUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [devices, setDevices] = useState<Device[]>([])
  const [total, setTotal] = useState(0)
  const [branches, setBranches] = useState<Branch[]>([])
  const [buildings, setBuildings] = useState<Building[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<Device | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)
  const [busyDeviceId, setBusyDeviceId] = useState<string | undefined>(undefined)

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState<DeviceStatusFilter>('')
  const [branchFilter, setBranchFilter] = useState('')
  const [buildingFilter, setBuildingFilter] = useState('')
  const [sort, setSortState] = useState<DeviceSort>('created_at:desc')

  const { page, goToNextPage, goToPrevPage, resetToFirstPage, setPage } = usePagedList()

  const canManage = canManageDevices(currentUser)

  const loadDevices = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false

      if (!silent) {
        setIsLoading(true)
        setErrorMessage(undefined)
      }

      try {
        const [user, devicePage, branchList, buildingList] = await Promise.all([
          getCurrentStaffUserUseCase.execute(),
          listDevicesPageUseCase.execute({
            operatingMode,
            page,
            pageSize: PAGE_SIZE,
            ...statusFilterToQuery(statusFilter),
            branchId: branchFilter || undefined,
            buildingId: buildingFilter || undefined,
            ...parseDeviceSort(sort),
          }),
          listBranchesUseCase.execute(),
          listBuildingsUseCase.execute(),
        ])
        setCurrentUser(user)
        setDevices(devicePage.items)
        setTotal(devicePage.total)
        setBranches(branchList)
        setBuildings(buildingList)
        setLastUpdatedAt(new Date())
      } catch (error) {
        const message =
          error instanceof ApiError && error.status === 403
            ? `You do not have permission to view ${noun}.`
            : `Something went wrong loading the ${noun}. Please try again.`
        if (!silent) setErrorMessage(message)
        toast.error(message)
      } finally {
        if (!silent) setIsLoading(false)
      }
    },
    [
      getCurrentStaffUserUseCase,
      listDevicesPageUseCase,
      listBranchesUseCase,
      listBuildingsUseCase,
      operatingMode,
      noun,
      page,
      statusFilter,
      branchFilter,
      buildingFilter,
      sort,
      toast,
    ],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadDevices()
  }, [navigate, loadDevices])

  const retry = useCallback(() => {
    void loadDevices()
  }, [loadDevices])

  const isActionInProgress = pendingDelete !== undefined || isDeleting || busyDeviceId !== undefined
  usePolling(() => void loadDevices({ silent: true }), { intervalMs: 15_000, isBusy: isActionInProgress })

  usePageRefresh({ refresh: retry, isRefreshing: isLoading, lastUpdatedAt })

  const isFiltering = statusFilter !== '' || branchFilter !== '' || buildingFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])

  const changeStatusFilter = useCallback(
    (value: string) => {
      setStatusFilter(value as DeviceStatusFilter)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeBranchFilter = useCallback(
    (value: string) => {
      setBranchFilter(value)
      setBuildingFilter('')
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeBuildingFilter = useCallback(
    (value: string) => {
      setBuildingFilter(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const changeSort = useCallback(
    (value: string) => {
      setSortState(value as DeviceSort)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const clearFilters = useCallback(() => {
    setStatusFilter('')
    setBranchFilter('')
    setBuildingFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

  const branchOptions = branches.map((branch) => ({ value: branch.id, label: branch.name })).sort((a, b) => a.label.localeCompare(b.label))
  const buildingOptions = buildings
    .filter((building) => !branchFilter || building.branchId === branchFilter)
    .map((building) => ({ value: building.id, label: building.name }))
    .sort((a, b) => a.label.localeCompare(b.label))

  // 404: another admin deleted it. 409: not approved (stale row). Either way the list is stale, so refresh.
  const reportMutationError = useCallback(
    (error: unknown, fallback: string) => {
      if (error instanceof ApiError && error.status === 404) {
        toast.error('That device no longer exists.')
        void loadDevices({ silent: true })
      } else if (error instanceof ApiError && error.status === 409) {
        toast.error(error.message)
        void loadDevices({ silent: true })
      } else if (error instanceof ApiError && (error.status === 403 || error.status === 422)) {
        toast.error(error.message)
      } else {
        toast.error(fallback)
      }
    },
    [toast, loadDevices],
  )

  const runAction = useCallback(
    async (action: DeviceAction, device: Device) => {
      const useCase = { approve: approveDeviceUseCase, enable: enableDeviceUseCase, disable: disableDeviceUseCase }[action]

      setBusyDeviceId(device.id)
      try {
        const updated = await useCase.execute(device.id)
        setDevices((current) => current.map((item) => (item.id === updated.id ? updated : item)))
        toast.success(ACTION_SUCCESS[action])
        // The updated row may no longer match the active status filter.
        await loadDevices({ silent: true })
      } catch (error) {
        reportMutationError(error, 'Something went wrong updating the device. Please try again.')
      } finally {
        setBusyDeviceId(undefined)
      }
    },
    [approveDeviceUseCase, enableDeviceUseCase, disableDeviceUseCase, toast, loadDevices, reportMutationError],
  )

  const approve = useCallback((device: Device) => runAction('approve', device), [runAction])
  const enable = useCallback((device: Device) => runAction('enable', device), [runAction])
  const disable = useCallback((device: Device) => runAction('disable', device), [runAction])

  const requestDelete = useCallback((device: Device) => setPendingDelete(device), [])
  const cancelDelete = useCallback(() => setPendingDelete(undefined), [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteDeviceUseCase.execute(pendingDelete.id)
      toast.success('Device deleted.')
      setPendingDelete(undefined)
      // Deleting the only row on a later page leaves that page empty: step back.
      if (devices.length === 1 && page > 1) {
        setPage(page - 1)
      } else {
        await loadDevices({ silent: true })
      }
    } catch (error) {
      setPendingDelete(undefined)
      reportMutationError(error, 'Something went wrong deleting the device. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteDeviceUseCase, devices.length, page, setPage, toast, loadDevices, reportMutationError])

  return {
    canManage,
    devices,
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
    branchFilter,
    setBranchFilter: changeBranchFilter,
    branchOptions,
    buildingFilter,
    setBuildingFilter: changeBuildingFilter,
    buildingOptions,
    sort,
    setSort: changeSort,
    clearFilters,
    isFiltering,
    busyDeviceId,
    approve,
    enable,
    disable,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
