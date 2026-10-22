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
import { BuildingsTable } from './Components/BuildingsTable'
import { useAdminBuildings } from './hooks/use-admin-buildings'

export function AdminBuildingsPage() {
  const navigate = useNavigate()
  const {
    buildings,
    total,
    page,
    pageSize,
    goToNextPage,
    goToPrevPage,
    phase,
    isRefreshing,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    branchOptions,
    branchFilter,
    setBranchFilter,
    statusFilter,
    setStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  } = useAdminBuildings()

  usePageHeader({ description: 'Administer branch premises, building access policies, and reception configurations' })

  const goToAddBuilding = () => navigate('/admin/buildings/new')

  // Pinned below the scrolling rows, not inside them, so it never scrolls
  // out of view (responsive-layout "Paged List Pagination Stays Visible
  // Below the Data").
  const pagination =
    phase === 'ready' && buildings.length > 0 ? (
      <div className="flex-none">
        <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
      </div>
    ) : undefined

  return (
    <PageContentLayout
      fitBody={buildings.length > 0}
      footer={pagination}
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Buildings Registry</h1>
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
                onClick={goToAddBuilding}
                className={`flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-on-accent hover:bg-admin-accent/90 ${PRESS_FEEDBACK_CLASS}`}
              >
                <PlusIcon className="size-3.5" />
                Add Building
              </button>
            </div>
          </div>

          <Collapsible open={isFilterPanelOpen} closedClassName={PAGE_HEADER_GAP_CANCEL}>
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-full sm:w-48">
                <SelectField label="Branch" value={branchFilter} onChange={setBranchFilter} placeholder="All" options={branchOptions} />
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
        skeleton={<TableSkeleton columns={6} rows={pageSize} label="Loading buildings…" />}
        errorMessage="Something went wrong loading the buildings. Please try again."
        onRetry={retry}
        isEmpty={buildings.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            {isFiltering ? (
              <EmptyState message="No buildings match these filters." />
            ) : (
              <EmptyState message="No buildings yet." action={{ label: 'Add Building', onClick: goToAddBuilding }} />
            )}
          </div>
        }
      >
        <BuildingsTable buildings={buildings} onDelete={requestDelete} />
      </AsyncRegion>

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Building"
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
