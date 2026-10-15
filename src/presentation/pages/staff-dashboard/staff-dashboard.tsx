import { CalendarIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { usePageHeader } from '../../context/page-header-context'
import { KpiRow } from '../../components/dashboard/KpiRow'
import { MyUpcomingVisitorsCard } from '../../components/dashboard/MyUpcomingVisitorsCard'
import { useStaffDashboard } from './hooks/use-staff-dashboard'

function greetingForHour(hour: number): string {
  if (hour < 12) return 'Good Morning'
  if (hour < 18) return 'Good Afternoon'
  return 'Good Evening'
}

const TODAY_LABEL = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' }).format(new Date())

export function StaffDashboardPage() {
  const { currentUser, overview, kpis, isLoading, errorMessage, retry, openVisit } = useStaffDashboard()

  const firstName = currentUser?.name.split(' ')[0] ?? ''
  const greeting = greetingForHour(new Date().getHours())

  usePageHeader({ description: 'Your visitors at a glance' })

  return (
    <>
      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading || !overview ? (
        <LoadingState label="Loading dashboard…" className="flex-1" />
      ) : (
        <>
          <div className="flex w-full flex-col gap-3 rounded-2xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between md:p-6">
            <div className="flex flex-col gap-1">
              <h1 className="font-display text-xl font-bold text-text">
                {greeting}{firstName ? `, ${firstName}` : ''}
              </h1>
              <p className="font-body text-sm text-text-faint">Here's how your visitors are doing today.</p>
            </div>
            <div className="flex items-center gap-2 font-body text-sm font-medium text-text-muted">
              <CalendarIcon className="size-4 text-admin-accent" />
              {TODAY_LABEL}
            </div>
          </div>

          <KpiRow kpis={kpis} />

          <MyUpcomingVisitorsCard visitors={overview.upcomingPreview} onOpen={openVisit} />
        </>
      )}
    </>
  )
}
