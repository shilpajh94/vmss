import { DropdownFilter } from '../../../components/ui/DropdownFilter'
import { SegmentedToggle } from '../../../components/ui/SegmentedToggle'
import { PRESS_FEEDBACK_CLASS } from '../../../components/ui/interactive'
import { ChevronLeftIcon, ChevronRightIcon, GitBranchIcon } from '../../../components/icons'
import { formatPeriodTitle, type CalendarView } from '../../../utils/calendar-dates'
import { CALENDAR_STATUS_FILTERS, calendarStatusStyle } from '../calendar-status'
import type { BranchOption } from '../../../hooks/use-branch-options'

const ALL_BRANCHES = ''
const VIEW_OPTIONS = [
  { value: 'month', label: 'Month' },
  { value: 'week', label: 'Week' },
  { value: 'day', label: 'Day' },
]

interface CalendarToolbarProps {
  view: CalendarView
  date: string
  onViewChange: (view: CalendarView) => void
  onShift: (direction: 1 | -1) => void
  onToday: () => void
  // Empty unless the feed is branch-wide and there's more than one branch.
  branchOptions: BranchOption[]
  branchId: string | undefined
  onBranchChange: (branchId: string | undefined) => void
  selectedStatuses: readonly string[]
  onToggleStatus: (status: string) => void
}

const NAV_BUTTON_CLASS = `flex size-10 items-center justify-center rounded-lg border border-border bg-surface text-text hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`

export function CalendarToolbar({
  view,
  date,
  onViewChange,
  onShift,
  onToday,
  branchOptions,
  branchId,
  onBranchChange,
  selectedStatuses,
  onToggleStatus,
}: CalendarToolbarProps) {
  const unit = view === 'month' ? 'month' : view === 'week' ? 'week' : 'day'

  return (
    <div className="flex w-full flex-col gap-3 rounded-2xl border border-border bg-surface p-3 md:p-4">
      <div className="flex w-full flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <button type="button" onClick={() => onShift(-1)} aria-label={`Previous ${unit}`} className={NAV_BUTTON_CLASS}>
            <ChevronLeftIcon className="size-4" />
          </button>
          <button type="button" onClick={() => onShift(1)} aria-label={`Next ${unit}`} className={NAV_BUTTON_CLASS}>
            <ChevronRightIcon className="size-4" />
          </button>
          <button
            type="button"
            onClick={onToday}
            className={`h-10 rounded-lg border border-border bg-surface px-3 font-body text-sm font-semibold text-text hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`}
          >
            Today
          </button>
          {/* Its own line on phones, so a long day title is never cut off. */}
          <h2 aria-live="polite" className="min-w-0 basis-full font-display text-lg font-semibold text-text sm:basis-auto sm:pl-1 md:text-xl">
            {formatPeriodTitle(view, date)}
          </h2>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {branchOptions.length > 0 ? (
            <DropdownFilter
              icon={GitBranchIcon}
              ariaLabel="Branch"
              value={branchId ?? ALL_BRANCHES}
              onChange={(value) => onBranchChange(value || undefined)}
              options={[{ value: ALL_BRANCHES, label: 'All branches' }, ...branchOptions.map((branch) => ({ value: branch.id, label: branch.name }))]}
            />
          ) : null}
          <div role="group" aria-label="Calendar view">
            <SegmentedToggle options={VIEW_OPTIONS} value={view} onChange={(value) => onViewChange(value as CalendarView)} />
          </div>
        </div>
      </div>
      <div role="group" aria-label="Show statuses" className="flex flex-wrap items-center gap-2">
        <span className="font-body text-xs font-semibold text-text-muted">Show:</span>
        {CALENDAR_STATUS_FILTERS.map((status) => {
          const style = calendarStatusStyle(status)
          const isOn = selectedStatuses.includes(status)
          return (
            <button
              key={status}
              type="button"
              aria-pressed={isOn}
              onClick={() => onToggleStatus(status)}
              className={`flex h-8 items-center gap-1.5 rounded-full border px-3 font-body text-xs font-semibold ${PRESS_FEEDBACK_CLASS} ${
                isOn ? `border-transparent text-text ${style.fillClass}` : 'border-border bg-surface text-text-faint line-through hover:text-text-muted'
              }`}
            >
              <span aria-hidden className={`size-2 rounded-full ${isOn ? style.dotClass : 'bg-border'}`} />
              {style.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
