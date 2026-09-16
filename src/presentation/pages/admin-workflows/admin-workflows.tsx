import { useNavigate } from 'react-router'
import { PlusIcon, RefreshCcwIcon, SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { usePageHeader } from '../../context/page-header-context'
import { WorkflowGroupList } from './Components/WorkflowGroupList'
import { useAdminWorkflows } from './hooks/use-admin-workflows'

export function AdminWorkflowsPage() {
  const navigate = useNavigate()
  const { workflows, isLoading, errorMessage, retry, pendingDelete, isDeleting, requestDelete, cancelDelete, confirmDelete } =
    useAdminWorkflows()

  usePageHeader({ description: 'Configure automated visitor check-in, alert triggers, and compliance workflows' })

  const goToAddWorkflow = () => navigate('/admin/workflows/new')

  return (
    <>
      <div className="flex w-full items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-text">Workflows</h1>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={retry}
            aria-label="Refresh"
            className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
          >
            <RefreshCcwIcon className="size-3.5" />
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
          >
            <SlidersIcon className="size-3.5" />
            Filters
          </button>
          <button
            type="button"
            onClick={goToAddWorkflow}
            className="flex items-center gap-2 rounded-full bg-admin-accent px-[18px] py-2.5 font-body text-[13px] font-semibold text-white"
          >
            <PlusIcon className="size-3.5" />
            Add Workflow
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
        <WorkflowGroupList workflows={workflows} onDelete={requestDelete} />
      )}

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Workflow"
        message={`Are you sure you want to delete the workflow for "${pendingDelete?.categoryName}"? This cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </>
  )
}
