import { SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { Pagination } from '../../components/Pagination'
import { PageContentLayout } from '../../components/PageContentLayout'
import { usePageHeader } from '../../context/page-header-context'
import type { DeviceOperatingMode } from '../../../domain/entities/managed-device-schema'
import { DevicesTable } from './Components/DevicesTable'
import { useAdminDevices } from './hooks/use-admin-devices'
import { DEVICE_SORT_OPTIONS, DEVICE_STATUS_OPTIONS } from './device-status-filter'

interface AdminDevicesListProps {
  operatingMode: DeviceOperatingMode
  /** Page heading, e.g. "Reception Desks". */
  title: string
  /** Lower-case plural used in messages, e.g. "reception desks". */
  noun: string
  description: string
}

// Shared body of the Reception Desks and Security Gates pages: both list
// devices from the same endpoint, differing only by operating mode.
export function AdminDevicesList({ operatingMode, title, noun, description }: AdminDevicesListProps) {
  const {
    canManage,
    devices,
    total,
    page,
    pageSize,
    goToNextPage,
    goToPrevPage,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    statusFilter,
    setStatusFilter,
    branchFilter,
    setBranchFilter,
    branchOptions,
    buildingFilter,
    setBuildingFilter,
    buildingOptions,
    sort,
    setSort,
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
  } = useAdminDevices(operatingMode, noun)

  usePageHeader({ description })

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">{title}</h1>
            <button
              type="button"
              onClick={toggleFilterPanel}
              className="flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text"
            >
              <SlidersIcon className="size-3.5" />
              Filters
            </button>
          </div>

          {isFilterPanelOpen && (
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-full sm:w-48">
                <SelectField
                  label="Status"
                  value={statusFilter}
                  onChange={setStatusFilter}
                  placeholder="All"
                  placeholderSelectable
                  options={DEVICE_STATUS_OPTIONS}
                />
              </div>
              <div className="w-full sm:w-48">
                <SelectField
                  label="Branch"
                  value={branchFilter}
                  onChange={setBranchFilter}
                  placeholder="All branches"
                  placeholderSelectable
                  options={branchOptions}
                />
              </div>
              <div className="w-full sm:w-48">
                <SelectField
                  label="Building"
                  value={buildingFilter}
                  onChange={setBuildingFilter}
                  placeholder="All buildings"
                  placeholderSelectable
                  options={buildingOptions}
                />
              </div>
              <div className="w-full sm:w-56">
                <SelectField label="Sort by" value={sort} onChange={setSort} options={DEVICE_SORT_OPTIONS} />
              </div>
              {isFiltering && (
                <button type="button" onClick={clearFilters} className="font-body text-[13px] font-semibold text-admin-accent">
                  Clear filters
                </button>
              )}
            </div>
          )}
        </>
      }
    >
      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label={`Loading ${noun}…`} className="flex-1" />
      ) : devices.length === 0 ? (
        <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
          <EmptyState message={isFiltering ? `No ${noun} match these filters.` : `No ${noun} registered yet.`} />
        </div>
      ) : (
        <div className="flex h-full flex-col gap-3">
          <DevicesTable
            devices={devices}
            canManage={canManage}
            busyDeviceId={busyDeviceId}
            onApprove={(device) => void approve(device)}
            onEnable={(device) => void enable(device)}
            onDisable={(device) => void disable(device)}
            onDelete={requestDelete}
          />
          <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      )}

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Device"
        message={`Are you sure you want to delete "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </PageContentLayout>
  )
}
