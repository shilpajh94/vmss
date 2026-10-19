import { useNavigate } from 'react-router'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { SelectField } from '../../components/ui/SelectField'
import { PAGE_HEADER_GAP_CANCEL, PageContentLayout } from '../../components/PageContentLayout'
import { AsyncRegion } from '../../components/AsyncRegion'
import { Collapsible } from '../../components/ui/Collapsible'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { PRESS_FEEDBACK_CLASS } from '../../components/ui/interactive'
import { usePageHeader } from '../../context/page-header-context'
import { WorkflowListTable } from './Components/WorkflowListTable'
import { useAdminWorkflows } from './hooks/use-admin-workflows'

export function AdminWorkflowsPage() {
  const navigate = useNavigate()
  const {
    workflows,
    pagedWorkflows,
    page,
    pageSize,
    totalPages,
    goToPreviousPage,
    goToNextPage,
    phase,
    isRefreshing,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    categoryOptions,
    categoryFilter,
    setCategoryFilter,
    statusFilter,
    setStatusFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  } = useAdminWorkflows()

  usePageHeader({ description: 'Configure automated visitor check-in, alert triggers, and compliance workflows' })

  const goToAddWorkflow = () => navigate('/admin/workflows/new')

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Workflows</h1>
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
                onClick={goToAddWorkflow}
                className={`flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white hover:bg-admin-accent/90 ${PRESS_FEEDBACK_CLASS}`}
              >
                <PlusIcon className="size-3.5" />
                Add Workflow
              </button>
            </div>
          </div>

          <Collapsible open={isFilterPanelOpen} closedClassName={PAGE_HEADER_GAP_CANCEL}>
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-full sm:w-48">
                <SelectField
                  label="Visitor Category"
                  value={categoryFilter}
                  onChange={setCategoryFilter}
                  placeholder="All"
                  options={categoryOptions}
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
        skeleton={<TableSkeleton columns={5} rows={pageSize} label="Loading workflows…" />}
        errorMessage="Something went wrong loading the workflows. Please try again."
        onRetry={retry}
        isEmpty={workflows.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            {isFiltering ? (
              <EmptyState message="No workflows match these filters." />
            ) : (
              <EmptyState message="No workflows yet." action={{ label: 'Add Workflow', onClick: goToAddWorkflow }} />
            )}
          </div>
        }
      >
        <WorkflowListTable
          workflows={workflows}
          pagedWorkflows={pagedWorkflows}
          page={page}
          pageSize={pageSize}
          totalPages={totalPages}
          onPreviousPage={goToPreviousPage}
          onNextPage={goToNextPage}
          onDelete={requestDelete}
        />
      </AsyncRegion>

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Workflow"
        message={`Are you sure you want to delete the workflow for "${pendingDelete?.categoryName}"? This cannot be undone.`}
        confirmLabel="Delete"
        isBusy={isDeleting}
        busyLabel="Deleting…"
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </PageContentLayout>
  )
}
