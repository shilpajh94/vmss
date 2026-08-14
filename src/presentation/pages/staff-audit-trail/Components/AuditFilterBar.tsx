import { CalendarIcon, SearchGlyphIcon, SlidersIcon } from '../../../components/icons'
import { ACTIVITY_TYPE_OPTIONS, DATE_RANGE_OPTIONS } from '../types'
import { DropdownFilter } from './DropdownFilter'

interface AuditFilterBarProps {
  dateRange: string
  onDateRangeChange: (value: string) => void
  activityType: string
  onActivityTypeChange: (value: string) => void
  search: string
  onSearchChange: (value: string) => void
}

export function AuditFilterBar({ dateRange, onDateRangeChange, activityType, onActivityTypeChange, search, onSearchChange }: AuditFilterBarProps) {
  return (
    <div className="flex w-full items-center gap-3 rounded-xl border border-border bg-surface p-4">
      <DropdownFilter icon={CalendarIcon} value={dateRange} options={DATE_RANGE_OPTIONS} onChange={onDateRangeChange} ariaLabel="Date range" />
      <DropdownFilter icon={SlidersIcon} value={activityType} options={ACTIVITY_TYPE_OPTIONS} onChange={onActivityTypeChange} ariaLabel="Activity type" />

      <div className="flex flex-1 items-center gap-2 rounded-lg border border-[#cbd5e1] bg-surface px-3 py-2.5">
        <SearchGlyphIcon className="size-4 shrink-0 text-text-faint" />
        <input
          type="text"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search visitor name..."
          className="flex-1 bg-transparent font-body text-[13px] text-text placeholder:text-text-faint focus:outline-none"
        />
      </div>
    </div>
  )
}
