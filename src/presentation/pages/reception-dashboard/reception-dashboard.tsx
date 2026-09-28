import { ReceptionSidebar } from '../../components/ReceptionSidebar'
import { CalendarIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { KpiRow } from '../../components/dashboard/KpiRow'
import { RecentCheckinsCard } from '../../components/dashboard/RecentCheckinsCard'
import { UpcomingVisitorsCard } from '../../components/dashboard/UpcomingVisitorsCard'
import { ReceptionTopBar } from './Components/ReceptionTopBar'
import { useReceptionDashboard } from './hooks/use-reception-dashboard'

function greetingForHour(hour: number): string {
  if (hour < 12) return 'Good Morning'
  if (hour < 18) return 'Good Afternoon'
  return 'Good Evening'
}

const TODAY_LABEL = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' }).format(new Date())

export function ReceptionDashboardPage() {
  const { currentUser, overview, kpis, recentCheckins, employeeNameById, isLoading, errorMessage, retry } = useReceptionDashboard()

  const firstName = currentUser?.name.split(' ')[0] ?? ''
  const greeting = greetingForHour(new Date().getHours())

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <ReceptionSidebar activeItem="dashboard" />

      <div className="flex flex-1 flex-col">
        <ReceptionTopBar description="A bird's-eye view of today's visitor activity" currentUser={currentUser} />

        <main className="flex flex-1 flex-col gap-6 p-8">
          {errorMessage ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
              <p className="font-body text-sm text-danger">{errorMessage}</p>
              <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
                Try again
              </button>
            </div>
          ) : isLoading || !overview ? (
            <LoadingState label="Loading dashboard…" className="flex-1" />
          ) : (
            <>
              <div className="flex w-full items-center justify-between rounded-2xl border border-border bg-surface p-6">
                <div className="flex flex-col gap-1">
                  <h1 className="font-display text-xl font-bold text-text">
                    {greeting}, {firstName}
                  </h1>
                  <p className="font-body text-sm text-text-faint">Here's a bird's-eye view of visitor activity today.</p>
                </div>
                <div className="flex items-center gap-2 font-body text-sm font-medium text-text-muted">
                  <CalendarIcon className="size-4 text-admin-accent" />
                  {TODAY_LABEL}
                </div>
              </div>

              <KpiRow kpis={kpis} />

              <RecentCheckinsCard checkins={recentCheckins} employeeNameById={employeeNameById} />

              <UpcomingVisitorsCard visitors={overview.upcomingVisitors} employeeNameById={employeeNameById} />
            </>
          )}
        </main>
      </div>
    </div>
  )
}
