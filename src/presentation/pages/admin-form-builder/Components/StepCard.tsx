import {
  CalendarIcon,
  CheckIcon,
  FileTextIcon,
  GridIcon,
  PencilIcon,
  ShieldIcon,
  UserIcon,
} from '../../../components/icons'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import type { FormStep } from '../../../../domain/entities/form-builder-schema'

const STEP_ICONS: Record<string, typeof UserIcon> = {
  user: UserIcon,
  calendar: CalendarIcon,
  briefcase: FileTextIcon,
  car: GridIcon,
  'shield-check': ShieldIcon,
  'check-circle': CheckIcon,
}

interface StepCardProps {
  step: FormStep
  order: number
  onToggleActive: () => void
  onEditFields: () => void
  onDelete: () => void
}

export function StepCard({ step, order, onToggleActive, onEditFields, onDelete }: StepCardProps) {
  const Icon = (step.icon && STEP_ICONS[step.icon]) || PencilIcon
  const fieldCount = step.fields.length

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-start justify-between">
        <span className="flex size-9 items-center justify-center rounded-lg bg-bg text-admin-accent">
          <Icon className="size-4.5" />
        </span>
        <div className="flex items-center gap-2">
          <span className="font-body text-[11px] font-bold tracking-wide text-text-faint uppercase">
            {step.isActive ? 'Active' : 'Inactive'}
          </span>
          <ToggleSwitch checked={step.isActive} onChange={onToggleActive} label="" />
        </div>
      </div>

      <div>
        <p className="flex items-baseline gap-2">
          <span className="font-body text-xs font-semibold text-text-muted">{order}</span>
          <span className="font-display text-base font-bold text-text">{step.name}</span>
        </p>
        <p className="font-body text-xs text-text-muted">
          {step.isSystem && step.fields.length === 0 && step.key === 'review_confirm'
            ? 'Auto-generated review sheet'
            : `${fieldCount} field${fieldCount === 1 ? '' : 's'} configured`}
        </p>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onEditFields}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-border bg-bg px-3 py-2 font-body text-[13px] font-semibold text-text"
        >
          <PencilIcon className="size-3.5" />
          Edit Fields
        </button>
        {!step.isLocked && (
          <button
            type="button"
            onClick={onDelete}
            className="rounded-lg border border-border px-3 py-2 font-body text-[13px] font-semibold text-danger"
          >
            Remove
          </button>
        )}
      </div>
    </div>
  )
}
