import { useNavigate } from 'react-router'
import { PlusIcon, SlidersIcon } from '../../components/icons'
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
import { FloorsTable } from './Components/FloorsTable'
import { useAdminFloors } from './hooks/use-admin-floors'

export function AdminFloorsPage() {
  const navigate = useNavigate()
  const {
    floors,
    total,
    page,
    pageSize,
    goToNextPage,
    goToPrevPage,
    departmentNamesByFloorId,
    phase,
    isRefreshing,
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
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Floors Inventory</h1>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={toggleFilterPanel}
                aria-expanded={isFilterPanelOpen}
                className={`flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`}
              >
                <SlidersIcon className="size-3.5" />
                Filters
              </button>
              <button
                type="button"
                onClick={goToAddFloor}
                className={`flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white hover:bg-admin-accent/90 ${PRESS_FEEDBACK_CLASS}`}
              >
                <PlusIcon className="size-3.5" />
                Add Floor
              </button>
            </div>
          </div>

          <Collapsible open={isFilterPanelOpen} closedClassName={PAGE_HEADER_GAP_CANCEL}>
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-full sm:w-48">
                <SelectField label="Building" value={buildingFilter} onChange={setBuildingFilter} placeholder="All" options={buildingOptions} />
              </div>
              <div className="w-full sm:w-48">
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
              <div className="w-full sm:w-48">
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
          </Collapsible>
        </>
      }
    >
      <AsyncRegion
        phase={phase}
        isRefreshing={isRefreshing}
        skeleton={<TableSkeleton columns={6} rows={pageSize} label="Loading floors…" />}
        errorMessage="Something went wrong loading the floors. Please try again."
        onRetry={retry}
        isEmpty={floors.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            {isFiltering ? (
              <EmptyState message="No floors match these filters." />
            ) : (
              <EmptyState message="No floors yet." action={{ label: 'Add Floor', onClick: goToAddFloor }} />
            )}
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          <FloorsTable floors={floors} departmentNamesByFloorId={departmentNamesByFloorId} onDelete={requestDelete} />
          <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      </AsyncRegion>

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Floor"
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
