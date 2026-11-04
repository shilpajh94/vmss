import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError } from '../../../../data/api/api-error'
import type { Zone, ZoneSortBy } from '../../../../domain/entities/zone-schema'
import { useToast } from '../../../components/toast/toast-context'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { usePermissions } from '../../../context/current-user-context'
import { useZoneFeature } from '../../../context/zone-feature-context'
import { useLiveResource } from '../../../hooks/use-live-resource'
import { usePagedList } from '../../../hooks/use-paged-list'
import { PAGE_PERMISSIONS } from '../../../route-permissions'
import { toUserMessage } from '../../../utils/to-user-message'
import { loadZoneReferenceData } from '../zone-reference-data'

const PAGE_SIZE = 20
const EMPTY_ZONES: Zone[] = []

// One select drives both the sort field and direction.
export const ZONE_SORT_OPTIONS = [
  { value: 'name:asc', label: 'Name (A–Z)' },
  { value: 'name:desc', label: 'Name (Z–A)' },
  { value: 'created_at:desc', label: 'Newest first' },
  { value: 'created_at:asc', label: 'Oldest first' },
]

function parseSort(value: string): { sortBy: ZoneSortBy; sortOrder: 'asc' | 'desc' } {
  const [sortBy, sortOrder] = value.split(':')
  return { sortBy: sortBy === 'created_at' ? 'created_at' : 'name', sortOrder: sortOrder === 'desc' ? 'desc' : 'asc' }
}

export function useAdminZones() {
  const dependencies = useAppDependencies()
  const { listZonesUseCase, deleteZoneUseCase } = dependencies
  const toast = useToast()
  const canManage = usePermissions().can(PAGE_PERMISSIONS.zonesManage)
  const { reportDisabled } = useZoneFeature()

  const [pendingDelete, setPendingDelete] = useState<Zone | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [branchFilter, setBranchFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sort, setSort] = useState(ZONE_SORT_OPTIONS[0].value)
  const { page, goToNextPage, goToPrevPage, resetToFirstPage } = usePagedList()

  const isActionInProgress = pendingDelete !== undefined || isDeleting
  const resource = useLiveResource({
    load: () =>
      listZonesUseCase.execute({
        page,
        pageSize: PAGE_SIZE,
        isActive: statusFilter === '' ? undefined : statusFilter === 'active',
        branchId: branchFilter || undefined,
        ...parseSort(sort),
      }),
    query: { page, statusFilter, branchFilter, sort },
    reference: () => loadZoneReferenceData(dependencies),
    errorMessage: (error) =>
      error instanceof ApiError && error.status === 404 ? 'Zone access is not enabled.' : 'Something went wrong loading the zones. Please try again.',
    isBusy: isActionInProgress,
  })
  const { phase, isRefreshing, retry, reload, error } = resource

  // A 404 from the zone API means the backend feature is off: hide the zone UI everywhere.
  const isFeatureOff = phase === 'error' && error instanceof ApiError && error.status === 404
  useEffect(() => {
    if (isFeatureOff) reportDisabled()
  }, [isFeatureOff, reportDisabled])

  const zones = resource.data?.data ?? EMPTY_ZONES
  const total = resource.data?.pagination.total ?? 0
  const references = resource.reference

  const branchOptions = useMemo(
    () => (references?.branches ?? []).map((branch) => ({ value: branch.id, label: branch.name })).sort((a, b) => a.label.localeCompare(b.label)),
    [references],
  )
  const names = useMemo(
    () => ({
      branch: new Map((references?.branches ?? []).map((branch) => [branch.id, branch.name])),
      building: new Map((references?.buildings ?? []).map((building) => [building.id, building.name])),
      floor: new Map((references?.floors ?? []).map((floor) => [floor.id, floor.name])),
      gate: new Map((references?.gates ?? []).map((gate) => [gate.id, gate.name])),
    }),
    [references],
  )

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return
    setIsDeleting(true)
    try {
      await deleteZoneUseCase.execute(pendingDelete.id)
      toast.success('Zone deleted.')
      setPendingDelete(undefined)
      await reload()
    } catch (deleteError) {
      toast.error(toUserMessage(deleteError, 'Something went wrong deleting the zone. Please try again.'))
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteZoneUseCase, toast, reload])

  const changeBranchFilter = useCallback(
    (value: string) => {
      setBranchFilter(value)
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
  const changeSort = useCallback(
    (value: string) => {
      setSort(value)
      resetToFirstPage()
    },
    [resetToFirstPage],
  )
  const clearFilters = useCallback(() => {
    setBranchFilter('')
    setStatusFilter('')
    resetToFirstPage()
  }, [resetToFirstPage])

  return {
    zones,
    total,
    page,
    pageSize: PAGE_SIZE,
    goToNextPage,
    goToPrevPage,
    phase,
    isRefreshing,
    retry,
    isFeatureOff,
    canManage,
    names,
    isFilterPanelOpen,
    toggleFilterPanel: useCallback(() => setIsFilterPanelOpen((current) => !current), []),
    branchOptions,
    branchFilter,
    setBranchFilter: changeBranchFilter,
    statusFilter,
    setStatusFilter: changeStatusFilter,
    sort,
    setSort: changeSort,
    clearFilters,
    isFiltering: branchFilter !== '' || statusFilter !== '',
    pendingDelete,
    isDeleting,
    requestDelete: setPendingDelete,
    cancelDelete: useCallback(() => setPendingDelete(undefined), []),
    confirmDelete,
  }
}
