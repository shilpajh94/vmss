import { useNavigate } from 'react-router'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { WorkflowGroup } from '../hooks/use-admin-workflows'

interface WorkflowGroupListProps {
  workflows: WorkflowGroup[]
  onDelete: (workflow: WorkflowGroup) => void
}

export function WorkflowGroupList({ workflows, onDelete }: WorkflowGroupListProps) {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col gap-4">
      {workflows.map((workflow) => (
        <div key={workflow.visitorCategoryId} className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-bold text-text">{workflow.categoryName}</h2>
            <div className="flex items-center gap-2">
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
          </div>
          <ol className="flex flex-col gap-2">
            {workflow.levels.map((level) => (
              <li key={level.ruleId} className="flex items-center gap-3 rounded-lg border border-border-subtle bg-bg px-4 py-2.5">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-secondary-accent/15 font-body text-xs font-bold text-secondary-accent">
                  {level.stepOrder}
                </span>
                <span className="font-body text-sm font-semibold text-text">{level.approverRoleName}</span>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}
