import { useNavigate } from 'react-router'
import { ChevronLeftIcon, ChevronRightIcon, PencilIcon, TrashIcon } from '../../../components/icons'
import type { WorkflowGroup } from '../hooks/use-admin-workflows'

interface WorkflowListTableProps {
  workflows: WorkflowGroup[]
  pagedWorkflows: WorkflowGroup[]
  page: number
  pageSize: number
  totalPages: number
  onPreviousPage: () => void
  onNextPage: () => void
  onDelete: (workflow: WorkflowGroup) => void
}

const COLUMN_HEADERS = ['Workflow', 'Status', 'Approval Flow', 'Levels']

export function WorkflowListTable({
  workflows,
  pagedWorkflows,
  page,
  pageSize,
  totalPages,
  onPreviousPage,
  onNextPage,
  onDelete,
}: WorkflowListTableProps) {
  const navigate = useNavigate()

  const total = workflows.length
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  return (
    <div className="flex w-full flex-col gap-6 rounded-2xl border border-border bg-surface p-6">
      <div className="flex flex-col gap-1">
        <h2 className="font-body text-sm font-bold text-text">Workflow List</h2>
        <p className="font-body text-[13px] text-text-muted">{total} workflows</p>
      </div>

      <div className="w-full overflow-x-auto rounded-xl border border-border-subtle">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-border-subtle">
              {COLUMN_HEADERS.map((header) => (
                <th key={header} className="px-6 py-3.5 font-body text-[13px] font-bold text-text-muted whitespace-nowrap">
                  {header}
                </th>
              ))}
              <th className="px-6 py-3.5 text-right font-body text-[13px] font-bold text-text-muted whitespace-nowrap">Actions</th>
            </tr>
          </thead>
          <tbody>
            {pagedWorkflows.map((workflow) => (
              <tr key={workflow.visitorCategoryId} className="border-b border-border-subtle last:border-b-0">
                <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">{workflow.categoryName}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-body text-xs font-semibold ${
                      workflow.status === 'active' ? 'bg-success/15 text-success' : 'bg-border-subtle text-text-muted'
                    }`}
                  >
                    <span className={`size-1.5 rounded-full ${workflow.status === 'active' ? 'bg-success' : 'bg-text-faint'}`} />
                    {workflow.status === 'active' ? 'Active' : 'Paused'}
                  </span>
                </td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">
                  {workflow.levels.map((level) => level.approverRoleName).join(' → ')}
                </td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{workflow.levels.length} levels</td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/admin/workflows/${workflow.visitorCategoryId}/edit`)}
                      aria-label={`Edit ${workflow.categoryName} workflow`}
                      className="flex items-center justify-center rounded-lg bg-border-subtle p-2 text-text"
                    >
                      <PencilIcon className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(workflow)}
                      aria-label={`Delete ${workflow.categoryName} workflow`}
                      className="flex items-center justify-center rounded-lg bg-danger/15 p-2 text-danger"
                    >
                      <TrashIcon className="size-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex w-full items-center justify-between border-t border-border pt-4">
        <p className="font-body text-[13px] text-text-muted">
          Showing {start}-{end} of {total} workflows
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onPreviousPage}
            disabled={page <= 1}
            aria-label="Previous page"
            className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3.5 py-2 font-body text-[13px] font-semibold text-text disabled:opacity-40"
          >
            <ChevronLeftIcon className="size-3.5" />
            Previous
          </button>
          <button
            type="button"
            onClick={onNextPage}
            disabled={page >= totalPages}
            aria-label="Next page"
            className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3.5 py-2 font-body text-[13px] font-semibold text-text disabled:opacity-40"
          >
            Next
            <ChevronRightIcon className="size-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}
