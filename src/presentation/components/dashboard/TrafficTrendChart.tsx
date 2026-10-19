import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard } from './ChartCard'
import { ChartTooltipContent } from './ChartTooltip'
import { useChartTheme } from './chart-theme'
import { formatDayLabel } from './dashboard-format'
import { useMediaQuery } from '../../hooks/use-media-query'
import type { DailyTrendPoint } from '../../../domain/entities/dashboard-analytics-schema'

interface TrafficTrendChartProps {
  title: string
  subtitle: string
  points: DailyTrendPoint[]
  isUpdating?: boolean
  className?: string
}

// Scheduled visits per day as a soft area, with the visits that were
// admitted and the no-shows as lines on the same scale (one axis: all three
// are counts of the same visits).
export function TrafficTrendChart({ title, subtitle, points, isUpdating, className }: TrafficTrendChartProps) {
  const theme = useChartTheme()
  const isPhone = !useMediaQuery('(min-width: 640px)')

  const series = [
    { key: 'scheduled', label: 'Scheduled', color: theme.scheduled },
    { key: 'checkedIn', label: 'Checked in', color: theme.checkedIn },
    { key: 'noShow', label: 'No-shows', color: theme.noShow },
  ] as const
  const totals = {
    scheduled: points.reduce((sum, point) => sum + point.scheduled, 0),
    checkedIn: points.reduce((sum, point) => sum + point.checkedIn, 0),
    noShow: points.reduce((sum, point) => sum + point.noShow, 0),
  }
  const summary = `Last ${points.length} days: ${totals.scheduled} scheduled, ${totals.checkedIn} checked in, ${totals.noShow} no-shows`
  // Thin the date labels so they never overlap: about 4 on a phone, 8 wider.
  const tickInterval = Math.max(0, Math.ceil(points.length / (isPhone ? 4 : 8)) - 1)

  return (
    <ChartCard
      title={title}
      subtitle={subtitle}
      summary={summary}
      isEmpty={totals.scheduled === 0}
      emptyMessage="No scheduled visits in this period."
      isUpdating={isUpdating}
      className={className}
      table={{
        columns: [
          { key: 'date', label: 'Date' },
          ...series.map((item) => ({ key: item.key, label: item.label })),
        ],
        rows: points.map((point) => ({ ...point, date: formatDayLabel(point.date) })),
      }}
    >
      <ul className="mb-3 flex flex-wrap gap-x-5 gap-y-1.5">
        {series.map((item) => (
          <li key={item.key} className="flex items-center gap-2 font-body text-xs text-text-muted">
            <span className="h-0.5 w-3.5 rounded-full" style={{ backgroundColor: item.color }} />
            {item.label}
            <span className="font-semibold text-text tabular-nums">{totals[item.key]}</span>
          </li>
        ))}
      </ul>
      <div className="h-[220px] w-full md:h-[260px] lg:h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 20, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke={theme.grid} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDayLabel}
              interval={tickInterval}
              tickLine={false}
              axisLine={{ stroke: theme.axis }}
              tick={{ fill: theme.mutedText, fontSize: 11 }}
              minTickGap={8}
              padding={{ left: 4, right: 4 }}
            />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: theme.mutedText, fontSize: 11 }} width={40} />
            <Tooltip
              cursor={{ stroke: theme.axis }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <ChartTooltipContent
                    title={formatDayLabel(String(label))}
                    rows={series.map((item) => ({
                      label: item.label,
                      color: item.color,
                      value: Number(payload[0].payload[item.key] ?? 0),
                    }))}
                  />
                ) : null
              }
            />
            <Area
              type="monotone"
              dataKey="scheduled"
              name="Scheduled"
              stroke={theme.scheduled}
              strokeWidth={2}
              fill={theme.scheduled}
              fillOpacity={0.12}
              activeDot={{ r: 4, stroke: theme.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="checkedIn"
              name="Checked in"
              stroke={theme.checkedIn}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: theme.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="noShow"
              name="No-shows"
              stroke={theme.noShow}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: theme.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
