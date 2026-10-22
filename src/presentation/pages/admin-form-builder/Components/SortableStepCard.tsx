import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVerticalIcon } from '../../../components/icons'
import { StepCard } from './StepCard'
import type { FormStep } from '../../../../domain/entities/form-builder-schema'

interface SortableStepCardProps {
  step: FormStep
  order: number
  onToggleActive: () => void
  onEditFields: () => void
  onDelete: () => void
}

/** Drag-and-drop wrapper around `StepCard`, used only for the non-locked
 * steps between the locked first-two and locked-last steps — those render
 * as a plain `StepCard` with no drag handle at all, so a locked step can
 * never be picked up in the UI (the server also rejects repositioning one,
 * per `form_builder/service.py`'s reorder guard).
 */
export function SortableStepCard({ step, order, onToggleActive, onEditFields, onDelete }: SortableStepCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: step.id })

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={isDragging ? 'opacity-60' : ''}
    >
      <StepCard
        step={step}
        order={order}
        onToggleActive={onToggleActive}
        onEditFields={onEditFields}
        onDelete={onDelete}
        dragHandle={
          <button
            type="button"
            {...attributes}
            {...listeners}
            aria-label="Drag to reorder"
            className="flex cursor-grab items-center justify-center text-text-faint active:cursor-grabbing max-lg:-m-3 max-lg:size-10"
          >
            <GripVerticalIcon className="size-4" />
          </button>
        }
      />
    </div>
  )
}
