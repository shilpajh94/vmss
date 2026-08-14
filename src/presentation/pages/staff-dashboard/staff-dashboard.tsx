import { DashboardSidebar } from './Components/DashboardSidebar'
import { KanbanColumn } from './Components/KanbanColumn'
import { SearchActionBar } from './Components/SearchActionBar'
import { WorkspaceHeader } from './Components/WorkspaceHeader'
import { useStaffDashboard } from './hooks/use-staff-dashboard'

const EMPTY_MESSAGES: Record<string, string> = {
  requested: 'No requested visits',
  approved: 'No approved visits',
  checked_in: 'No checked-in visitors today',
  denied: 'No denied visits',
}

export function StaffDashboardPage() {
  const { currentUser, columns, isLoading, errorMessage, search, setSearch, refresh, signOut } = useStaffDashboard()

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <DashboardSidebar />

      <main className="flex flex-1 flex-col gap-6 p-8">
        <WorkspaceHeader currentUser={currentUser} onRefresh={refresh} onSignOut={signOut} />
        <SearchActionBar search={search} onSearchChange={setSearch} onRefresh={refresh} />

        {errorMessage ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
            <p className="font-body text-sm text-danger">{errorMessage}</p>
            <button type="button" onClick={refresh} className="rounded-lg bg-secondary-accent px-4 py-2 font-body text-sm font-semibold text-white">
              Try again
            </button>
          </div>
        ) : isLoading ? (
          <div className="flex flex-1 items-center justify-center">
            <p className="font-body text-sm text-text-muted">Loading visit requests…</p>
          </div>
        ) : (
          <div className="flex w-full flex-1 items-start gap-4">
            {columns.map((column) => (
              <KanbanColumn
                key={column.status}
                status={column.status}
                label={column.label}
                requests={column.requests}
                emptyMessage={EMPTY_MESSAGES[column.status]}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
