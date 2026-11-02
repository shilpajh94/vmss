import { useCallback, useState } from 'react'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useCurrentUser } from '../../../context/current-user-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePagedList } from '../../../hooks/use-paged-list'
import { useLiveResource } from '../../../hooks/use-live-resource'
import { ApiError } from '../../../../data/api/api-error'
import type { Device, DeviceOperatingMode } from '../../../../domain/entities/managed-device-schema'
import type { Branch } from '../../../../domain/entities/branch-schema'
import type { Building } from '../../../../domain/entities/building-schema'
import { canManageDevices } from '../can-manage-devices'
import { parseDeviceSort, statusFilterToQuery, type DeviceSort, type DeviceStatusFilter } from '../device-status-filter'

const PAGE_SIZE = 20
const EMPTY_DEVICES: Device[] = []
const EMPTY_BRANCHES: Branch[] = []
const EMPTY_BUILDINGS: Building[] = []

type DeviceAction = 'approve' | 'enable' | 'disable'

const ACTION_SUCCESS: Record<DeviceAction, string> = {
  approve: 'Device approved.',
  enable: 'Device enabled.',
  disable: 'Device disabled.',
}

export function useAdminDevices(operatingMode: DeviceOperatingMode, noun: string) {
  const {
    listDevicesPageUseCase,
    approveDeviceUseCase,
    enableDeviceUseCase,
    disableDeviceUseCase,
    deleteDeviceUseCase,
    listBranchesUseCase,
    listBuildingsUseCase,
  } = useAppDependencies()
  const toast = useToast()

  const currentUser = useCurrentUser()

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

  const loadErrorText = useCallback(
    (error: unknown) =>
      error instanceof ApiError && error.status === 403
        ? `You do not have permission to view ${noun}.`
        : `Something went wrong loading the ${noun}. Please try again.`,
    [noun],
  )

  // The device rows are the live data; the branch and building filter
  // options load once. Polls skip while a dialog or row action is busy.
  const isActionInProgress = pendingDelete !== undefined || isDeleting || busyDeviceId !== undefined
  const resource = useLiveResource({
    load: () =>
      listDevicesPageUseCase.execute({
        operatingMode,
        page,
        pageSize: PAGE_SIZE,
        ...statusFilterToQuery(statusFilter),
        branchId: branchFilter || undefined,
        buildingId: buildingFilter || undefined,
        ...parseDeviceSort(sort),
      }),
    query: { operatingMode, page, statusFilter, branchFilter, buildingFilter, sort },
    reference: async () => {
      const [branches, buildings] = await Promise.all([listBranchesUseCase.execute(), listBuildingsUseCase.execute()])
      return { branches, buildings }
    },
    errorMessage: loadErrorText,
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, reload, setData } = resource
  const devices = resource.data?.items ?? EMPTY_DEVICES
  const total = resource.data?.total ?? 0
  const branches = resource.reference?.branches ?? EMPTY_BRANCHES
  const buildings = resource.reference?.buildings ?? EMPTY_BUILDINGS
  // Only shown when the first load fails; keeps the 403 vs generic wording.
  const loadErrorMessage = phase === 'error' ? loadErrorText(resource.error) : undefined

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
        void reload()
      } else if (error instanceof ApiError && error.status === 409) {
        toast.error(error.message)
        void reload()
      } else if (error instanceof ApiError && (error.status === 403 || error.status === 422)) {
        toast.error(error.message)
      } else {
        toast.error(fallback)
      }
    },
    [toast, reload],
  )

  const runAction = useCallback(
    async (action: DeviceAction, device: Device) => {
      const useCase = { approve: approveDeviceUseCase, enable: enableDeviceUseCase, disable: disableDeviceUseCase }[action]

      setBusyDeviceId(device.id)
      try {
        const updated = await useCase.execute(device.id)
        setData((current) => current && { ...current, items: current.items.map((item) => (item.id === updated.id ? updated : item)) })
        toast.success(ACTION_SUCCESS[action])
        // The updated row may no longer match the active status filter.
        await reload()
      } catch (error) {
        reportMutationError(error, 'Something went wrong updating the device. Please try again.')
      } finally {
        setBusyDeviceId(undefined)
      }
    },
    [approveDeviceUseCase, enableDeviceUseCase, disableDeviceUseCase, toast, setData, reload, reportMutationError],
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
        await reload()
      }
    } catch (error) {
      setPendingDelete(undefined)
      reportMutationError(error, 'Something went wrong deleting the device. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteDeviceUseCase, devices.length, page, setPage, toast, reload, reportMutationError])

  return {
    canManage,
    devices,
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
