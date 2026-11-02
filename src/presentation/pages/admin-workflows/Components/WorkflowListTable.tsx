import { useNavigate } from 'react-router'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { WorkflowGroup } from '../hooks/use-admin-workflows'
import { responsiveTableClassName } from '../../../components/ui/responsive-table'
import { StatusBadge } from '../../../components/ui/StatusBadge'

// Below `md`: only the identifying, status, and actions columns stay visible.
const TABLE_CLASS_NAME = responsiveTableClassName([3, 4])

interface WorkflowListTableProps {
  workflows: WorkflowGroup[]
  pagedWorkflows: WorkflowGroup[]
  onDelete: (workflow: WorkflowGroup) => void
}

const COLUMN_HEADERS = ['Workflow', 'Status', 'Approval Flow', 'Levels']

export function WorkflowListTable({
  workflows,
  pagedWorkflows,
  onDelete,
}: WorkflowListTableProps) {
  const navigate = useNavigate()

  const total = workflows.length

  return (
    <div className="flex w-full flex-col gap-6 rounded-2xl border border-border bg-surface p-4 md:p-6">
      <div className="flex flex-col gap-1">
        <h2 className="font-body text-sm font-bold text-text">Workflow List</h2>
        <p className="font-body text-[13px] text-text-muted">{total} workflows</p>
      </div>

      <div className="w-full overflow-x-auto rounded-xl border border-border-subtle">
        <table className={TABLE_CLASS_NAME}>
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
                  <StatusBadge isActive={workflow.status === 'active'} inactiveLabel="Paused" />
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
                      className="flex items-center justify-center rounded-lg bg-border-subtle p-2 max-lg:p-3 text-text"
                    >
                      <PencilIcon className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(workflow)}
                      aria-label={`Delete ${workflow.categoryName} workflow`}
                      className="flex items-center justify-center rounded-lg bg-danger/15 p-2 max-lg:p-3 text-danger"
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
    </div>
  )
}
