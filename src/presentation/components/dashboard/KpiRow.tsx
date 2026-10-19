import type { ComponentType, SVGProps } from 'react'
import { Link } from 'react-router'
import { CalendarCheckIcon, ChevronRightIcon, ClockIcon, UserCheckIcon, UsersIcon } from '../icons'

export type DashboardKpiKey = 'visits-today' | 'checked-in' | 'pending-approval' | 'upcoming-visitors'

export interface DashboardKpiTile {
  key: DashboardKpiKey
  label: string
  value: number
  // One live secondary line, e.g. "4 checked in so far".
  detail?: string
  // The invitations board, filtered to what the tile counts.
  href: string
}

const KPI_ICONS: Record<DashboardKpiKey, ComponentType<SVGProps<SVGSVGElement>>> = {
  'visits-today': UsersIcon,
  'checked-in': UserCheckIcon,
  'pending-approval': CalendarCheckIcon,
  'upcoming-visitors': ClockIcon,
}

// Each tile is one link to the matching invitations (dashboard-insights "KPI
// Tiles Link to the Matching Invitations").
export function KpiRow({ kpis }: { kpis: DashboardKpiTile[] }) {
  return (
    <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6 lg:grid-cols-4">
      {kpis.map((kpi) => {
        const Icon = KPI_ICONS[kpi.key]

        return (
          <Link
            key={kpi.key}
            to={kpi.href}
            aria-label={`${kpi.label}: ${kpi.value}${kpi.detail ? `, ${kpi.detail}` : ''}. View these invitations`}
            className="group flex min-h-[132px] flex-col justify-between gap-4 rounded-2xl border border-border bg-surface p-5 transition-colors hover:border-admin-accent/40 hover:bg-admin-accent/[0.03] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-admin-accent"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="font-body text-sm text-text-muted">{kpi.label}</p>
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-admin-accent/10">
                <Icon className="size-4 text-admin-accent" />
              </span>
            </div>

            <div className="flex items-end justify-between gap-3">
              <div className="flex min-w-0 flex-col gap-1">
                <p className="font-display text-[28px] leading-none font-bold text-text">{kpi.value}</p>
                {kpi.detail ? <p className="truncate font-body text-xs text-text-faint">{kpi.detail}</p> : null}
              </div>
              <ChevronRightIcon className="size-4 shrink-0 text-text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-admin-accent" />
            </div>
          </Link>
        )
      })}
    </div>
  )
}
