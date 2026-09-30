import { useNavigate } from 'react-router'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { Pagination } from '../../components/Pagination'
import { PageContentLayout } from '../../components/PageContentLayout'
import { usePageHeader } from '../../context/page-header-context'
import { ReceptionDesksTable } from './Components/ReceptionDesksTable'
import { useAdminReceptionDesks } from './hooks/use-admin-reception-desks'

export function AdminReceptionDesksPage() {
  const navigate = useNavigate()
  const {
    receptionDesks,
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
    buildingOptions,
    buildingFilter,
    setBuildingFilter,
    floorOptions,
    floorFilter,
    setFloorFilter,
    statusFilter,
    setStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  } = useAdminReceptionDesks()

  usePageHeader({ description: 'Manage on-site registration desks, kiosks, and building entrance welcoming nodes' })

  const goToAddReceptionDesk = () => navigate('/admin/reception-desks/new')

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Reception Desks Register</h1>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={toggleFilterPanel}
                className="flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text"
              >
                <SlidersIcon className="size-3.5" />
                Filters
              </button>
              <button
                type="button"
                onClick={goToAddReceptionDesk}
                className="flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white"
              >
                <PlusIcon className="size-3.5" />
                Add Desk
              </button>
            </div>
          </div>

          {isFilterPanelOpen && (
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-full sm:w-48">
                <SelectField label="Building" value={buildingFilter} onChange={setBuildingFilter} placeholder="All" options={buildingOptions} />
              </div>
              <div className="w-full sm:w-48">
                <SelectField label="Floor" value={floorFilter} onChange={setFloorFilter} placeholder="All" options={floorOptions} />
              </div>
              <div className="w-full sm:w-48">
                <SelectField
                  label="Status"
                  value={statusFilter}
                  onChange={setStatusFilter}
                  placeholder="All"
                  options={[
                    { value: 'active', label: 'Active' },
                    { value: 'maintenance', label: 'Maintenance' },
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
        <LoadingState label="Loading reception desks…" className="flex-1" />
      ) : receptionDesks.length === 0 ? (
        <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
          {isFiltering ? (
            <EmptyState message="No reception desks match these filters." />
          ) : (
            <EmptyState message="No reception desks yet." action={{ label: 'Add Desk', onClick: goToAddReceptionDesk }} />
          )}
        </div>
      ) : (
        <div className="flex h-full flex-col gap-3">
          <ReceptionDesksTable receptionDesks={receptionDesks} onDelete={requestDelete} />
          <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      )}

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Reception Desk"
        message={`Are you sure you want to delete "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </PageContentLayout>
  )
}
