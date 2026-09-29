import { useNavigate } from 'react-router'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { Pagination } from '../../components/Pagination'
import { PageContentLayout } from '../../components/PageContentLayout'
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
    isLoading,
    errorMessage,
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
          <div className="flex w-full items-center justify-between">
            <h1 className="font-display text-2xl font-bold text-text">Kiosks</h1>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={toggleFilterPanel}
                className="flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text"
              >
                <SlidersIcon className="size-3.5" />
                Filters
              </button>
              {canManage && (
                <button
                  type="button"
                  onClick={goToAddKiosk}
                  className="flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white"
                >
                  <PlusIcon className="size-3.5" />
                  Add Kiosk
                </button>
              )}
            </div>
          </div>

          {isFilterPanelOpen && (
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-48">
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
              <div className="w-48">
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
          )}
        </>
      }
    >
      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading kiosks…" className="flex-1" />
      ) : kiosks.length === 0 ? (
        <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
          {isFiltering ? (
            <EmptyState message="No kiosks match these filters." />
          ) : canManage ? (
            <EmptyState message="No kiosks yet." action={{ label: 'Add Kiosk', onClick: goToAddKiosk }} />
          ) : (
            <EmptyState message="No kiosks yet." />
          )}
        </div>
      ) : (
        <div className="flex h-full flex-col gap-3">
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
      )}

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Kiosk"
        message={`Are you sure you want to delete "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </PageContentLayout>
  )
}
