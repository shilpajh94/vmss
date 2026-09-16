import { useNavigate } from 'react-router'
import { PlusIcon, RefreshCcwIcon, SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { usePageHeader } from '../../context/page-header-context'
import { FloorsTable } from './Components/FloorsTable'
import { useAdminFloors } from './hooks/use-admin-floors'

export function AdminFloorsPage() {
  const navigate = useNavigate()
  const {
    floors,
    hasAnyFloors,
    departmentNamesByFloorId,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    buildingOptions,
    buildingFilter,
    setBuildingFilter,
    accessLevelFilter,
    setAccessLevelFilter,
    statusFilter,
    setStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  } = useAdminFloors()

  usePageHeader({ description: 'Manage building floors, occupancy capacity limits, and access group clearance' })

  const goToAddFloor = () => navigate('/admin/floors/new')

  return (
    <>
      <div className="flex w-full items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-text">Floors Inventory</h1>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={retry}
            aria-label="Refresh"
            className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
          >
            <RefreshCcwIcon className="size-3.5" />
          </button>
          <button
            type="button"
            onClick={toggleFilterPanel}
            className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
          >
            <SlidersIcon className="size-3.5" />
            Filters
          </button>
          <button
            type="button"
            onClick={goToAddFloor}
            className="flex items-center gap-2 rounded-full bg-admin-accent px-[18px] py-2.5 font-body text-[13px] font-semibold text-white"
          >
            <PlusIcon className="size-3.5" />
            Add Floor
          </button>
        </div>
      </div>

      {isFilterPanelOpen && (
        <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-4">
          <div className="w-48">
            <SelectField label="Building" value={buildingFilter} onChange={setBuildingFilter} placeholder="All" options={buildingOptions} />
          </div>
          <div className="w-48">
            <SelectField
              label="Access Level"
              value={accessLevelFilter}
              onChange={setAccessLevelFilter}
              placeholder="All"
              options={[
                { value: 'public', label: 'Public' },
                { value: 'restricted', label: 'Restricted' },
                { value: 'secure', label: 'Secure' },
              ]}
            />
          </div>
          <div className="w-48">
            <SelectField
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              placeholder="All"
              options={[
                { value: 'active', label: 'Active' },
                { value: 'inactive', label: 'Inactive' },
              ]}
            />
          </div>
          {isFiltering && (
            <button type="button" onClick={clearFilters} className="font-body text-[13px] font-semibold text-admin-accent">
              Clear filters
            </button>
          )}
        </div>
      )}

      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading floors…" className="flex-1" />
      ) : floors.length === 0 ? (
        <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
          {hasAnyFloors ? (
            <EmptyState message="No floors match these filters." />
          ) : (
            <EmptyState message="No floors yet." action={{ label: 'Add Floor', onClick: goToAddFloor }} />
          )}
        </div>
      ) : (
        <FloorsTable floors={floors} departmentNamesByFloorId={departmentNamesByFloorId} onDelete={requestDelete} />
      )}

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Floor"
        message={`Are you sure you want to delete "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </>
  )
}
