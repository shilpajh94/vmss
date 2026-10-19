import { SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { SelectField } from '../../components/ui/SelectField'
import { Pagination } from '../../components/Pagination'
import { PAGE_HEADER_GAP_CANCEL, PageContentLayout } from '../../components/PageContentLayout'
import { AsyncRegion } from '../../components/AsyncRegion'
import { Collapsible } from '../../components/ui/Collapsible'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { PRESS_FEEDBACK_CLASS } from '../../components/ui/interactive'
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
    phase,
    isRefreshing,
    loadErrorMessage,
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
              aria-expanded={isFilterPanelOpen}
              className={`flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`}
            >
              <SlidersIcon className="size-3.5" />
              Filters
            </button>
          </div>

          <Collapsible open={isFilterPanelOpen} closedClassName={PAGE_HEADER_GAP_CANCEL}>
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
          </Collapsible>
        </>
      }
    >
      <AsyncRegion
        phase={phase}
        isRefreshing={isRefreshing}
        skeleton={<TableSkeleton columns={7} rows={pageSize} label={`Loading ${noun}…`} />}
        errorMessage={loadErrorMessage}
        onRetry={retry}
        isEmpty={devices.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            <EmptyState message={isFiltering ? `No ${noun} match these filters.` : `No ${noun} registered yet.`} />
          </div>
        }
      >
        <div className="flex flex-col gap-3">
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
      </AsyncRegion>

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Device"
        message={`Are you sure you want to delete "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        isBusy={isDeleting}
        busyLabel="Deleting…"
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </PageContentLayout>
  )
}
