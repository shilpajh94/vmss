import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GridIcon, PencilIcon, TrashIcon, XIcon } from '../../../components/icons'
import { ExpandableText } from '../../../components/ui/ExpandableText'
import { fieldTypeLabel } from '../field-type-catalog'
import type { FormField } from '../../../../domain/entities/form-builder-schema'

interface SortableFieldRowProps {
  field: FormField
  isSelected: boolean
  onSelect: () => void
  onToggleRequired: () => void
  onDelete: () => void
}

export function SortableFieldRow({ field, isSelected, onSelect, onToggleRequired, onDelete }: SortableFieldRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: field.id })

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${
        isSelected ? 'border-admin-accent bg-admin-accent/5' : 'border-border bg-surface'
      } ${isDragging ? 'opacity-60' : ''}`}
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
        className="cursor-grab text-text-faint active:cursor-grabbing"
      >
        <GridIcon className="size-4" />
      </button>

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <button type="button" onClick={onSelect} className="flex w-full items-center gap-3 text-left">
          {field.isLocked && <XIcon className="size-3.5 shrink-0 text-text-faint" />}
          <span className="font-body text-sm font-semibold text-text">{field.label}</span>
          <span className="rounded-full bg-bg px-2 py-0.5 font-body text-[11px] font-medium text-text-muted">
            {fieldTypeLabel(field.fieldType)}
          </span>
          {!field.isActive && (
            <span className="rounded-full bg-neutral-subtle px-2 py-0.5 font-body text-[11px] font-medium text-text-faint">
              Inactive
            </span>
          )}
        </button>
        <ExpandableText text={field.helpText} />
      </div>

      <label className="flex items-center gap-2">
        <span className="font-body text-xs font-medium text-text-muted">Required</span>
        <input
          type="checkbox"
          role="switch"
          checked={field.isRequired}
          disabled={field.isLocked}
          onChange={onToggleRequired}
          className="size-4 disabled:opacity-50"
        />
      </label>

      <button type="button" onClick={onSelect} aria-label="Edit field" className="text-text-faint hover:text-text">
        <PencilIcon className="size-4" />
      </button>
      {!field.isLocked && (
        <button type="button" onClick={onDelete} aria-label="Delete field" className="text-danger">
          <TrashIcon className="size-4" />
        </button>
      )}
    </div>
  )
}
