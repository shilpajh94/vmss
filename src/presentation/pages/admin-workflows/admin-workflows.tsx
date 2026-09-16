import { useNavigate } from 'react-router'
import { AdminSidebar } from '../../components/AdminSidebar'
import { AdminTopBar } from '../../components/AdminTopBar'
import { PlusIcon, RefreshCcwIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { WorkflowListTable } from './Components/WorkflowListTable'
import { useAdminWorkflows } from './hooks/use-admin-workflows'

export function AdminWorkflowsPage() {
  const navigate = useNavigate()
  const {
    currentUser,
    workflows,
    pagedWorkflows,
    page,
    pageSize,
    totalPages,
    goToPreviousPage,
    goToNextPage,
    isLoading,
    errorMessage,
    retry,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  } = useAdminWorkflows()

  const goToAddWorkflow = () => navigate('/admin/workflows/new')

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <AdminSidebar activeItem="workflows" />

      <div className="flex flex-1 flex-col">
        <AdminTopBar description="Configure automated visitor check-in, alert triggers, and compliance workflows" currentUser={currentUser} />

        <main className="flex flex-1 flex-col gap-6 p-8">
          <div className="flex w-full items-center justify-between">
            <div className="flex flex-col gap-1">
              <h1 className="font-display text-2xl font-bold text-text">Workflows</h1>
              <p className="font-body text-[13px] text-text-muted">
                Review active workflows, monitor status, and manage approvals across the organization
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={retry}
                aria-label="Refresh workflows"
                className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
              >
                <RefreshCcwIcon className="size-3.5" />
                Refresh
              </button>
              <button
                type="button"
                onClick={goToAddWorkflow}
                aria-label="Create Workflow"
                className="flex items-center gap-2 rounded-full bg-admin-accent px-[18px] py-2.5 font-body text-[13px] font-semibold text-white"
              >
                <PlusIcon className="size-3.5" />
                Create Workflow
              </button>
            </div>
          </div>

          {errorMessage ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
              <p className="font-body text-sm text-danger">{errorMessage}</p>
              <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
                Try again
              </button>
            </div>
          ) : isLoading ? (
            <LoadingState label="Loading workflows…" className="flex-1" />
          ) : workflows.length === 0 ? (
            <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
              <EmptyState message="No workflows yet." action={{ label: 'Add Workflow', onClick: goToAddWorkflow }} />
            </div>
          ) : (
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
          )}
        </main>
      </div>

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Workflow"
        message={`Are you sure you want to delete the workflow for "${pendingDelete?.categoryName}"? This cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </div>
  )
}
