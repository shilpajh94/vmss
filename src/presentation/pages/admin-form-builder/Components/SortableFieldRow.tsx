import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GridIcon, PencilIcon, TrashIcon, XIcon } from '../../../components/icons'
import { ExpandableText } from '../../../components/ui/ExpandableText'
import { CONTENT_ONLY_FIELD_TYPES, DELETE_LOCKED_SYSTEM_FIELD_KEYS, fieldTypeLabel } from '../field-type-catalog'
import type { FormField, FormFieldGroup } from '../../../../domain/entities/form-builder-schema'

const UNGROUPED_VALUE = '__ungrouped__'

interface SortableFieldRowProps {
  field: FormField
  isSelected: boolean
  onSelect: () => void
  onToggleRequired: () => void
  onDelete: () => void
  /** The step's groups, for the group-assignment dropdown — empty when the
   * step has none, in which case the dropdown doesn't render at all
   * (add-repeatable-field-groups). */
  groups: FormFieldGroup[]
  onAssignGroup: (groupId: string | null) => void
}

export function SortableFieldRow({ field, isSelected, onSelect, onToggleRequired, onDelete, groups, onAssignGroup }: SortableFieldRowProps) {
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
        className="flex cursor-grab items-center justify-center text-text-faint active:cursor-grabbing max-lg:-m-3 max-lg:size-10"
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

      {groups.length > 0 && (
        <select
          value={field.groupId ?? UNGROUPED_VALUE}
          onChange={(event) => onAssignGroup(event.target.value === UNGROUPED_VALUE ? null : event.target.value)}
          aria-label="Assign to group"
          className="rounded-lg border border-border bg-surface px-2 py-1.5 font-body text-xs text-text focus:outline-none focus:ring-2 focus:ring-admin-accent"
        >
          <option value={UNGROUPED_VALUE}>Ungrouped</option>
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
      )}

      {!CONTENT_ONLY_FIELD_TYPES.includes(field.fieldType) && (
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
      )}

      <button type="button" onClick={onSelect} aria-label="Edit field" className="text-text-faint hover:text-text">
        <PencilIcon className="size-4" />
      </button>
      {!field.isLocked && !DELETE_LOCKED_SYSTEM_FIELD_KEYS.has(field.key) && (
        <button type="button" onClick={onDelete} aria-label="Delete field" className="text-danger">
          <TrashIcon className="size-4" />
        </button>
      )}
    </div>
  )
}
