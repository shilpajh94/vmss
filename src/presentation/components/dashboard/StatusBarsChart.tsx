import { BarList } from './BarList'
import { ChartCard } from './ChartCard'
import { STATUS_LABELS, boardStatusPath, type BoardBasePath } from './dashboard-format'
import type { StatusCount } from '../../../domain/entities/dashboard-analytics-schema'

// The board's own status colours, so a status looks the same on both pages.
const STATUS_BAR_CLASSES: Record<string, string> = {
  submitted: 'bg-info',
  approved: 'bg-success',
  checked_in: 'bg-secondary-accent',
  checked_out: 'bg-text-faint',
  denied: 'bg-danger',
  archived: 'bg-warning',
}

interface StatusBarsChartProps {
  title: string
  statuses: StatusCount[]
  rangeDays: number
  boardBasePath: BoardBasePath
  isUpdating?: boolean
  className?: string
}

// Visits in the period by status: one labeled bar per status, in lifecycle
// order, each opening the board on that status. Bars rather than a donut —
// see VMMS_WEB design.md W7.
export function StatusBarsChart({ title, statuses, rangeDays, boardBasePath, isUpdating, className }: StatusBarsChartProps) {
  const total = statuses.reduce((sum, row) => sum + row.count, 0)
  const summary = `${total} visits in the last ${rangeDays} days: ${statuses
    .map((row) => `${row.count} ${STATUS_LABELS[row.status] ?? row.status}`)
    .join(', ')}`

  return (
    <ChartCard
      title={title}
      subtitle={`${total} visits · last ${rangeDays} days`}
      summary={summary}
      isEmpty={total === 0}
      emptyMessage="No visits in this period."
      isUpdating={isUpdating}
      className={className}
    >
      <BarList
        valueLabel="visits"
        items={statuses.map((row) => ({
          key: row.status,
          label: STATUS_LABELS[row.status] ?? row.status,
          value: row.count,
          barClassName: STATUS_BAR_CLASSES[row.status] ?? 'bg-text-faint',
          href: boardStatusPath(boardBasePath, row.status),
        }))}
      />
    </ChartCard>
  )
}
