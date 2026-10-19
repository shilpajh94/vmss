import { useNavigate } from 'react-router'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { SelectField } from '../../components/ui/SelectField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { Pagination } from '../../components/Pagination'
import { PAGE_HEADER_GAP_CANCEL, PageContentLayout } from '../../components/PageContentLayout'
import { AsyncRegion } from '../../components/AsyncRegion'
import { Collapsible } from '../../components/ui/Collapsible'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { PRESS_FEEDBACK_CLASS } from '../../components/ui/interactive'
import { usePageHeader } from '../../context/page-header-context'
import { KiosksTable } from './Components/KiosksTable'
import { useAdminKiosks } from './hooks/use-admin-kiosks'

const SORT_OPTIONS = [
  { value: 'name:asc', label: 'Name (A–Z)' },
  { value: 'name:desc', label: 'Name (Z–A)' },
  { value: 'created_at:desc', label: 'Newest first' },
  { value: 'created_at:asc', label: 'Oldest first' },
]

export function AdminKiosksPage() {
  const navigate = useNavigate()
  const {
    canManage,
    kiosks,
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
    showHidden,
    setShowHidden,
    sort,
    setSort,
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
  } = useAdminKiosks()

  usePageHeader({ description: 'Manage the company-wide check-in kiosks' })

  const goToAddKiosk = () => navigate('/admin/kiosks/new')

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Kiosks</h1>
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
              {canManage && (
                <button
                  type="button"
                  onClick={goToAddKiosk}
                  className={`flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white hover:bg-admin-accent/90 ${PRESS_FEEDBACK_CLASS}`}
                >
                  <PlusIcon className="size-3.5" />
                  Add Kiosk
                </button>
              )}
            </div>
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
                  options={[
                    { value: 'active', label: 'Active' },
                    { value: 'inactive', label: 'Inactive' },
                  ]}
                />
              </div>
              <div className="w-full sm:w-48">
                <SelectField label="Sort by" value={sort} onChange={setSort} options={SORT_OPTIONS} />
              </div>
              <div className="w-48 pb-2">
                <ToggleSwitch label="Show hidden" checked={showHidden} onChange={setShowHidden} />
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
        skeleton={<TableSkeleton columns={canManage ? 4 : 3} rows={pageSize} label="Loading kiosks…" />}
        errorMessage={loadErrorMessage}
        onRetry={retry}
        isEmpty={kiosks.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            {isFiltering ? (
              <EmptyState message="No kiosks match these filters." />
            ) : canManage ? (
              <EmptyState message="No kiosks yet." action={{ label: 'Add Kiosk', onClick: goToAddKiosk }} />
            ) : (
              <EmptyState message="No kiosks yet." />
            )}
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          <KiosksTable
            kiosks={kiosks}
            canManage={canManage}
            busyKioskId={busyKioskId}
            onToggleActive={(kiosk) => void toggleActive(kiosk)}
            onToggleHidden={(kiosk) => void toggleHidden(kiosk)}
            onDelete={requestDelete}
          />
          <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      </AsyncRegion>

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Kiosk"
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
