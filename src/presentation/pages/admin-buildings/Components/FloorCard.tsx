import { ChevronDownIcon, PencilIcon, PlusIcon, TrashIcon } from '../../../components/icons'
import type { Checkpoint, Floor } from '../../../../domain/entities/building-schema'

interface FloorCardProps {
  floor: Floor
  isExpanded: boolean
  onToggleExpand: () => void
  onEdit: () => void
  onDelete: () => void
  onAddCheckpoint: () => void
  onEditCheckpoint: (checkpoint: Checkpoint) => void
  onDeleteCheckpoint: (checkpoint: Checkpoint) => void
}

export function FloorCard({
  floor,
  isExpanded,
  onToggleExpand,
  onEdit,
  onDelete,
  onAddCheckpoint,
  onEditCheckpoint,
  onDeleteCheckpoint,
}: FloorCardProps) {
  return (
    <div
      className={`flex w-full flex-col gap-3 rounded-2xl border p-4 ${
        isExpanded ? 'border-[#99f6e4] bg-[#f0fdfa]' : 'border-border bg-border-subtle'
      }`}
    >
      <div className="flex w-full items-center justify-between">
        <button type="button" onClick={onToggleExpand} className="flex items-center gap-2.5">
          <span className="font-body text-sm font-semibold text-text">{floor.name}</span>
          <ChevronDownIcon className={`size-3.5 text-text-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
        </button>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onEdit}
            aria-label={`Edit ${floor.name}`}
            className="flex size-8 items-center justify-center rounded-lg border border-border bg-surface"
          >
            <PencilIcon className="size-4" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            aria-label={`Delete ${floor.name}`}
            className="flex size-8 items-center justify-center rounded-lg border border-border bg-surface"
          >
            <TrashIcon className="size-4" />
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="flex flex-col gap-3 pl-4">
          <div className="flex w-full items-center justify-between">
            <p className="font-body text-sm font-semibold text-text-muted">Security Checkpoints</p>
            <button
              type="button"
              onClick={onAddCheckpoint}
              className="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 font-body text-[13px] font-semibold text-admin-accent"
            >
              <PlusIcon className="size-4" />
              Add Checkpoint
            </button>
          </div>

          <div className="flex flex-col gap-2">
            {floor.checkpoints.map((checkpoint) => (
              <div key={checkpoint.id} className="flex w-full items-center gap-3 rounded-xl border border-border bg-surface px-3 py-2.5">
                <div className="flex flex-1 flex-col gap-0.5">
                  <p className="font-body text-sm font-semibold text-text">{checkpoint.name}</p>
                  <p className="font-body text-xs text-text-faint">Security checkpoint</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onEditCheckpoint(checkpoint)}
                    aria-label={`Edit ${checkpoint.name}`}
                    className="flex size-8 items-center justify-center rounded-lg border border-border bg-surface"
                  >
                    <PencilIcon className="size-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteCheckpoint(checkpoint)}
                    aria-label={`Delete ${checkpoint.name}`}
                    className="flex size-8 items-center justify-center rounded-lg border border-border bg-surface"
                  >
                    <TrashIcon className="size-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
