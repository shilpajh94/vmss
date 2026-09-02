import { useNavigate } from 'react-router'
import { AdminSidebar } from '../../components/AdminSidebar'
import { AdminTopBar } from '../../components/AdminTopBar'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { VisitorCategoriesTable } from './Components/VisitorCategoriesTable'
import { useAdminVisitorCategories } from './hooks/use-admin-visitor-categories'

export function AdminVisitorCategoriesPage() {
  const navigate = useNavigate()
  const {
    currentUser,
    visitorCategories,
    hasAnyVisitorCategories,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    badgeColorFilter,
    setBadgeColorFilter,
    ndaRequirementFilter,
    setNdaRequirementFilter,
    escortRequirementFilter,
    setEscortRequirementFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  } = useAdminVisitorCategories()

  const goToAddCategory = () => navigate('/admin/visitor-categories/new')

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <AdminSidebar activeItem="visitor-categories" />

      <div className="flex flex-1 flex-col">
        <AdminTopBar
          description="Define visitor classifications, compliance procedures, security rules and physical pass designs"
          currentUser={currentUser}
        />

        <main className="flex flex-1 flex-col gap-6 p-8">
          <div className="flex w-full items-center justify-between">
            <h1 className="font-display text-2xl font-bold text-text">Visitor Categories Registry</h1>
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
                onClick={goToAddCategory}
                className="flex items-center gap-2 rounded-full bg-admin-accent px-[18px] py-2.5 font-body text-[13px] font-semibold text-white"
              >
                <PlusIcon className="size-3.5" />
                Add Category
              </button>
            </div>
          </div>

          {isFilterPanelOpen && (
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-4">
              <div className="w-48">
                <SelectField
                  label="Badge Color"
                  value={badgeColorFilter}
                  onChange={setBadgeColorFilter}
                  placeholder="All"
                  options={[
                    { value: 'blue', label: 'Blue' },
                    { value: 'orange', label: 'Orange' },
                    { value: 'gold', label: 'Gold' },
                    { value: 'grey', label: 'Grey' },
                  ]}
                />
              </div>
              <div className="w-48">
                <SelectField
                  label="NDA Requirement"
                  value={ndaRequirementFilter}
                  onChange={setNdaRequirementFilter}
                  placeholder="All"
                  options={[
                    { value: 'digital', label: 'Yes (Digital)' },
                    { value: 'signed_pdf', label: 'Yes (Signed PDF)' },
                    { value: 'optional', label: 'Optional' },
                    { value: 'none', label: 'Not Required' },
                  ]}
                />
              </div>
              <div className="w-48">
                <SelectField
                  label="Escort Requirement"
                  value={escortRequirementFilter}
                  onChange={setEscortRequirementFilter}
                  placeholder="All"
                  options={[
                    { value: 'self_escort', label: 'Self-Escort' },
                    { value: 'access_logs_only', label: 'Access Logs Only' },
                    { value: 'always_required', label: 'Always Required' },
                    { value: 'gate_check_in_only', label: 'Gate Check-in Only' },
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
            <LoadingState label="Loading visitor categories…" className="flex-1" />
          ) : visitorCategories.length === 0 ? (
            <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
              {hasAnyVisitorCategories ? (
                <EmptyState message="No visitor categories match these filters." />
              ) : (
                <EmptyState message="No visitor categories yet." action={{ label: 'Add Category', onClick: goToAddCategory }} />
              )}
            </div>
          ) : (
            <VisitorCategoriesTable visitorCategories={visitorCategories} onDelete={requestDelete} />
          )}
        </main>
      </div>

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Visitor Category"
        message={`Are you sure you want to delete "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </div>
  )
}
