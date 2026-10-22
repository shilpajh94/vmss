import type { ReactNode } from 'react'
import { CalendarIcon } from '../icons'
import { currentHourIn, formatLongDate, greetingForHour } from './dashboard-format'

interface DashboardGreetingProps {
  firstName: string | undefined
  subtitle: string
  // The server's tenant-local date and timezone, so the label rolls over
  // with the data rather than with the browser's clock.
  today: string
  timezone: string | undefined
  // Range toggle and branch selector.
  controls?: ReactNode
}

export function DashboardGreeting({ firstName, subtitle, today, timezone, controls }: DashboardGreetingProps) {
  const greeting = greetingForHour(currentHourIn(timezone))

  return (
    <div className="flex w-full flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="font-display text-xl font-bold text-text">
          {greeting}
          {firstName ? `, ${firstName}` : ''}
        </h1>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 font-body text-sm text-text-faint">
          <span className="flex items-center gap-1.5 font-medium text-text-muted">
            <CalendarIcon className="size-4 text-admin-accent" />
            {formatLongDate(today)}
          </span>
          <span className="hidden sm:inline">·</span>
          <span>{subtitle}</span>
        </p>
      </div>
      {controls ? <div className="flex flex-wrap items-center gap-2">{controls}</div> : null}
    </div>
  )
}
