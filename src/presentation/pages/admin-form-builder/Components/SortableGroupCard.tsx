import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GridIcon } from '../../../components/icons'
import { GroupCard } from './GroupCard'
import type { FormField, FormFieldGroup, FormFieldGroupUpdateInput } from '../../../../domain/entities/form-builder-schema'

interface SortableGroupCardProps {
  group: FormFieldGroup
  fieldCount: number
  siblingFields: FormField[]
  onSaveProperties: (input: FormFieldGroupUpdateInput) => Promise<string | undefined>
  onDelete: () => void
}

/** Drag-and-drop wrapper around `GroupCard` — only used for non-locked
 * groups (`admin-form-builder-step-editor.tsx` renders a locked group as a
 * plain `GroupCard` with no drag handle at all), matching
 * `SortableStepCard`'s own convention for locked steps.
 */
export function SortableGroupCard({ group, fieldCount, siblingFields, onSaveProperties, onDelete }: SortableGroupCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: group.id })

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={isDragging ? 'opacity-60' : ''}
    >
      <GroupCard
        group={group}
        fieldCount={fieldCount}
        siblingFields={siblingFields}
        onSaveProperties={onSaveProperties}
        onDelete={onDelete}
        dragHandle={
          <button
            type="button"
            {...attributes}
            {...listeners}
            aria-label="Drag to reorder group"
            className="cursor-grab text-text-faint active:cursor-grabbing"
          >
            <GridIcon className="size-4" />
          </button>
        }
      />
    </div>
  )
}
