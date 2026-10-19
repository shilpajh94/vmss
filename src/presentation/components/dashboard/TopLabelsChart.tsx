import { useState } from 'react'
import { BarList } from './BarList'
import { ChartCard } from './ChartCard'
import type { LabelCount } from '../../../domain/entities/dashboard-analytics-schema'

type Dimension = 'purposes' | 'departments'

interface TopLabelsChartProps {
  purposes: LabelCount[]
  departments: LabelCount[]
  rangeDays: number
  isUpdating?: boolean
  className?: string
}

// The top purposes or departments by scheduled visits, switchable in place.
// One hue for every bar: the bars rank one measure, they don't name series.
export function TopLabelsChart({ purposes, departments, rangeDays, isUpdating, className }: TopLabelsChartProps) {
  const [dimension, setDimension] = useState<Dimension>('purposes')
  const rows = dimension === 'purposes' ? purposes : departments
  const noun = dimension === 'purposes' ? 'purpose' : 'department'
  const total = rows.reduce((sum, row) => sum + row.count, 0)

  return (
    <ChartCard
      title={dimension === 'purposes' ? 'Top Purposes' : 'Top Departments'}
      subtitle={`Scheduled visits · last ${rangeDays} days`}
      summary={`Scheduled visits by ${noun}, last ${rangeDays} days: ${rows.map((row) => `${row.label} ${row.count}`).join(', ')}`}
      isEmpty={total === 0}
      emptyMessage="No scheduled visits in this period."
      isUpdating={isUpdating}
      className={className}
      actions={
        <div role="group" aria-label="Group visits by" className="inline-flex overflow-hidden rounded-lg border border-border">
          {(['purposes', 'departments'] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={dimension === option}
              onClick={() => setDimension(option)}
              className={`min-h-10 px-3 font-body text-[13px] font-semibold capitalize transition-colors lg:min-h-9 ${
                dimension === option ? 'bg-admin-accent text-white' : 'text-text-muted hover:bg-admin-accent/10 hover:text-text'
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      }
    >
      <BarList
        valueLabel="visits"
        items={rows.map((row) => ({
          key: row.label,
          label: row.label,
          value: row.count,
          barClassName: row.label === 'Other' || row.label === 'Not specified' ? 'bg-text-faint' : 'bg-admin-accent',
        }))}
      />
    </ChartCard>
  )
}
