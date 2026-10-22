import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartCard } from './ChartCard'
import { ChartTooltipContent } from './ChartTooltip'
import { useChartTheme } from './chart-theme'
import { currentHourIn, formatHour } from './dashboard-format'
import { useMediaQuery } from '../../hooks/use-media-query'
import type { HourlyCheckIns } from '../../../domain/entities/dashboard-analytics-schema'

interface HourlyArrivalsChartProps {
  hours: HourlyCheckIns[]
  timezone: string
  className?: string
}

// Check-ins per hour of today in the tenant's timezone; the current hour is
// drawn solid and the rest lighter, so "now" stands out without a second hue.
export function HourlyArrivalsChart({ hours, timezone, className }: HourlyArrivalsChartProps) {
  const theme = useChartTheme()
  // Every 6 hours on a phone, every 3 wider, so labels never crowd.
  const tickInterval = useMediaQuery('(min-width: 640px)') ? 2 : 5
  const nowHour = currentHourIn(timezone)
  const total = hours.reduce((sum, row) => sum + row.count, 0)
  const peak = hours.reduce((best, row) => (row.count > best.count ? row : best), hours[0] ?? { hour: 0, count: 0 })
  const summary = total
    ? `Today: ${total} check-ins, busiest at ${formatHour(peak.hour)} with ${peak.count}`
    : 'No check-ins yet today'

  return (
    <ChartCard
      title="Arrivals Today"
      subtitle={total ? `${total} check-ins · busiest ${formatHour(peak.hour)}` : 'Check-ins by hour'}
      summary={summary}
      isEmpty={total === 0}
      emptyMessage="No visitors have checked in yet today."
      className={className}
      table={{
        columns: [
          { key: 'hour', label: 'Hour' },
          { key: 'count', label: 'Check-ins' },
        ],
        rows: hours.map((row) => ({ hour: formatHour(row.hour), count: row.count })),
      }}
    >
      <div className="h-[200px] w-full md:h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={hours} margin={{ top: 8, right: 12, bottom: 0, left: -20 }} barCategoryGap={2}>
            <CartesianGrid vertical={false} stroke={theme.grid} />
            <XAxis
              dataKey="hour"
              tickFormatter={formatHour}
              interval={tickInterval}
              tickLine={false}
              axisLine={{ stroke: theme.axis }}
              tick={{ fill: theme.mutedText, fontSize: 11 }}
            />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: theme.mutedText, fontSize: 11 }} width={36} />
            <Tooltip
              cursor={{ fill: theme.grid }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <ChartTooltipContent
                    title={`${formatHour(Number(payload[0].payload.hour))}${Number(payload[0].payload.hour) === nowHour ? ' (now)' : ''}`}
                    rows={[{ label: 'Check-ins', value: Number(payload[0].payload.count), color: theme.accent }]}
                  />
                ) : null
              }
            />
            <Bar dataKey="count" name="Check-ins" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {hours.map((row) => (
                <Cell key={row.hour} fill={theme.accent} fillOpacity={row.hour === nowHour ? 1 : 0.45} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  )
}
