import { useNavigate } from 'react-router'
import { AdminSidebar } from '../../components/AdminSidebar'
import { AdminTopBar } from '../../components/AdminTopBar'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { BuildingsTable } from './Components/BuildingsTable'
import { useAdminBuildings } from './hooks/use-admin-buildings'

export function AdminBuildingsPage() {
  const navigate = useNavigate()
  const {
    currentUser,
    buildings,
    hasAnyBuildings,
    isLoading,
    errorMessage,
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

  const goToAddBuilding = () => navigate('/admin/buildings/new')

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <AdminSidebar activeItem="buildings" />

      <div className="flex flex-1 flex-col">
        <AdminTopBar
          description="Administer branch premises, building access policies, and reception configurations"
          currentUser={currentUser}
        />

        <main className="flex flex-1 flex-col gap-6 p-8">
          <div className="flex w-full items-center justify-between">
            <h1 className="font-display text-2xl font-bold text-text">Buildings Registry</h1>
            <div className="flex items-center gap-3">
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
                onClick={goToAddBuilding}
                className="flex items-center gap-2 rounded-full bg-admin-accent px-[18px] py-2.5 font-body text-[13px] font-semibold text-white"
              >
                <PlusIcon className="size-3.5" />
                Add Building
              </button>
            </div>
          </div>

          {isFilterPanelOpen && (
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-4">
              <div className="w-48">
                <SelectField label="Branch" value={branchFilter} onChange={setBranchFilter} placeholder="All" options={branchOptions} />
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
            <LoadingState label="Loading buildings…" className="flex-1" />
          ) : buildings.length === 0 ? (
            <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
              {hasAnyBuildings ? (
                <EmptyState message="No buildings match these filters." />
              ) : (
                <EmptyState message="No buildings yet." action={{ label: 'Add Building', onClick: goToAddBuilding }} />
              )}
            </div>
          ) : (
            <BuildingsTable buildings={buildings} onDelete={requestDelete} />
          )}
        </main>
      </div>

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Building"
        message={`Are you sure you want to delete "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </div>
  )
}
