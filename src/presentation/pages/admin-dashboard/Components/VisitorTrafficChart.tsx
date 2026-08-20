import { EmptyState } from '../../../components/ui/EmptyState'
import type { DashboardTrafficPoint } from '../../../../domain/entities/dashboard-overview-schema'

interface VisitorTrafficChartProps {
  points: DashboardTrafficPoint[]
}

const CHART_WIDTH = 1000
const CHART_HEIGHT = 160

export function VisitorTrafficChart({ points }: VisitorTrafficChartProps) {
  if (points.length === 0) {
    return <EmptyState message="No traffic data for this period." className="py-12" />
  }

  const maxCount = Math.max(...points.map((point) => point.count), 1)
  const yMax = Math.max(Math.ceil(maxCount / 4) * 4, 4)
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((fraction) => Math.round(yMax * fraction))

  const stepX = points.length > 1 ? CHART_WIDTH / (points.length - 1) : 0
  const toY = (count: number) => CHART_HEIGHT - (count / yMax) * CHART_HEIGHT

  const linePoints = points.map((point, index) => `${index * stepX},${toY(point.count)}`)
  const linePath = `M${linePoints.join(' L')}`
  const areaPath = `${linePath} L${(points.length - 1) * stepX},${CHART_HEIGHT} L0,${CHART_HEIGHT} Z`

  return (
    <div className="flex w-full gap-3">
      <div className="flex flex-col justify-between" style={{ height: CHART_HEIGHT }}>
        {[...ticks].reverse().map((tick) => (
          <span key={tick} className="font-body text-xs text-text-faint">
            {tick}
          </span>
        ))}
      </div>

      <div className="flex flex-1 flex-col gap-2">
        <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} preserveAspectRatio="none" className="h-40 w-full">
          {ticks.map((tick) => (
            <line key={tick} x1={0} x2={CHART_WIDTH} y1={toY(tick)} y2={toY(tick)} stroke="var(--color-border-subtle)" strokeWidth={1} />
          ))}
          <path d={areaPath} fill="var(--color-admin-accent)" fillOpacity={0.12} stroke="none" />
          <path d={linePath} fill="none" stroke="var(--color-admin-accent)" strokeWidth={2} />
          {points.map((point, index) => (
            <circle key={point.day} cx={index * stepX} cy={toY(point.count)} r={3} fill="var(--color-admin-accent)" />
          ))}
        </svg>

        <div className="flex w-full justify-between">
          {points.map((point) => (
            <span key={point.day} className="font-body text-xs text-text-faint">
              {point.day}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
