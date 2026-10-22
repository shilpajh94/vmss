import type { DashboardRange } from '../../../domain/entities/dashboard-analytics-schema'

const OPTIONS: { value: DashboardRange; label: string }[] = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
]

// The chart period switch (dashboard-insights "Range Toggle Switches Chart
// Periods"); one per dashboard, applying to every period-based chart.
export function RangeToggle({ value, onChange }: { value: DashboardRange; onChange: (range: DashboardRange) => void }) {
  return (
    <div role="group" aria-label="Chart period" className="inline-flex shrink-0 overflow-hidden rounded-lg border border-border bg-surface">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`min-h-10 px-3 font-body text-[13px] font-semibold transition-colors duration-standard lg:min-h-9 ${
            value === option.value ? 'bg-admin-accent text-on-accent' : 'text-text-muted hover:bg-admin-accent/10 hover:text-text'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
