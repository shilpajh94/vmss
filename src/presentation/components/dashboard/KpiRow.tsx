import type { ComponentType, SVGProps } from 'react'
import { CalendarCheckIcon, ClockIcon, UserCheckIcon, UsersIcon } from '../icons'
import type { DashboardKpi } from '../../../domain/entities/dashboard-overview-schema'

interface KpiRowProps {
  kpis: DashboardKpi[]
}

const KPI_ICONS: Record<string, ComponentType<SVGProps<SVGSVGElement>>> = {
  'visits-today': UsersIcon,
  'checked-in': UserCheckIcon,
  'pending-approval': CalendarCheckIcon,
  'upcoming-visitors': ClockIcon,
}

export function KpiRow({ kpis }: KpiRowProps) {
  return (
    <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6 lg:grid-cols-4">
      {kpis.map((kpi) => {
        const Icon = KPI_ICONS[kpi.key] ?? UsersIcon

        return (
          <div key={kpi.key} className="flex flex-col gap-5 rounded-2xl border border-border bg-surface p-5">
            <div className="flex items-center justify-between">
              <p className="font-body text-sm text-text-muted">{kpi.label}</p>
              <span className="flex size-8 items-center justify-center rounded-lg bg-admin-accent/10">
                <Icon className="size-4 text-admin-accent" />
              </span>
            </div>

            <p className="font-display text-[28px] font-bold text-text">{kpi.value}</p>
          </div>
        )
      })}
    </div>
  )
}
