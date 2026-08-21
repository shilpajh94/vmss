import type { ComponentType, SVGProps } from 'react'
import { CalendarCheckIcon, ClockIcon, TrendingDownIcon, TrendingUpIcon, UserCheckIcon, UsersIcon } from '../../../components/icons'
import type { DashboardKpi } from '../../../../domain/entities/dashboard-overview-schema'

interface KpiRowProps {
  kpis: DashboardKpi[]
}

const KPI_ICONS: Record<string, ComponentType<SVGProps<SVGSVGElement>>> = {
  'todays-visitors': UsersIcon,
  'currently-on-site': UserCheckIcon,
  'pre-registered': CalendarCheckIcon,
  'average-visit-duration': ClockIcon,
}

export function KpiRow({ kpis }: KpiRowProps) {
  return (
    <div className="grid w-full grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {kpis.map((kpi) => {
        const Icon = KPI_ICONS[kpi.key] ?? UsersIcon
        const TrendIcon = kpi.trendDirection === 'up' ? TrendingUpIcon : TrendingDownIcon

        return (
          <div key={kpi.key} className="flex flex-col gap-5 rounded-2xl border border-border bg-surface p-5">
            <div className="flex items-center justify-between">
              <p className="font-body text-sm text-text-muted">{kpi.label}</p>
              <span className="flex size-8 items-center justify-center rounded-lg bg-admin-accent/10">
                <Icon className="size-4 text-admin-accent" />
              </span>
            </div>

            <div className="flex flex-col gap-1.5">
              <p className="font-display text-[28px] font-bold text-text">{kpi.value}</p>
              <div className={`flex items-center gap-1.5 font-body text-[13px] font-medium ${kpi.trendDirection === 'up' ? 'text-success' : 'text-danger'}`}>
                <TrendIcon className="size-3.5" />
                <span>{kpi.trendCaption}</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
