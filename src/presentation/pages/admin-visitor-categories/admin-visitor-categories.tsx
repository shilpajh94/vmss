import { useNavigate } from 'react-router'
import { PlusIcon, SlidersIcon, UploadIcon } from '../../components/icons'
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
import { BulkAddCategoriesModal } from './Components/BulkAddCategoriesModal'
import { VisitorCategoriesTable } from './Components/VisitorCategoriesTable'
import { useAdminVisitorCategories } from './hooks/use-admin-visitor-categories'

export function AdminVisitorCategoriesPage() {
  const navigate = useNavigate()
  const {
    visitorCategories,
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
    isBulkAddOpen,
    openBulkAdd,
    closeBulkAdd,
    isBulkCreating,
    bulkCreateResult,
    submitBulkAdd,
  } = useAdminVisitorCategories()

  usePageHeader({ description: 'Define visitor classifications, compliance procedures, security rules and physical pass designs' })

  const goToAddCategory = () => navigate('/admin/visitor-categories/new')

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Visitor Categories Registry</h1>
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
                onClick={openBulkAdd}
                className={`flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`}
              >
                <UploadIcon className="size-3.5" />
                Bulk Add
              </button>
              <button
                type="button"
                onClick={goToAddCategory}
                className={`flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-on-accent hover:bg-admin-accent/90 ${PRESS_FEEDBACK_CLASS}`}
              >
                <PlusIcon className="size-3.5" />
                Add Category
              </button>
            </div>
          </div>

          <Collapsible open={isFilterPanelOpen} closedClassName={PAGE_HEADER_GAP_CANCEL}>
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-full sm:w-48">
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
              <div className="w-full sm:w-48">
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
              <div className="w-full sm:w-48">
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
          </Collapsible>
        </>
      }
    >
      <AsyncRegion
        phase={phase}
        isRefreshing={isRefreshing}
        skeleton={<TableSkeleton columns={8} rows={pageSize} label="Loading visitor categories…" />}
        errorMessage="Something went wrong loading the visitor categories. Please try again."
        onRetry={retry}
        isEmpty={visitorCategories.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            {isFiltering ? (
              <EmptyState message="No visitor categories match these filters." />
            ) : (
              <EmptyState message="No visitor categories yet." action={{ label: 'Add Category', onClick: goToAddCategory }} />
            )}
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          <VisitorCategoriesTable visitorCategories={visitorCategories} onDelete={requestDelete} />
          <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      </AsyncRegion>

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Visitor Category"
        message={`Are you sure you want to delete "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        isBusy={isDeleting}
        busyLabel="Deleting…"
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />

      <BulkAddCategoriesModal
        isOpen={isBulkAddOpen}
        onClose={closeBulkAdd}
        onSubmit={(names) => void submitBulkAdd(names)}
        isSubmitting={isBulkCreating}
        result={bulkCreateResult}
      />
    </PageContentLayout>
  )
}
