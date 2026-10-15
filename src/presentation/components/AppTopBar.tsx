import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { LogOutIcon, RefreshCcwIcon } from './icons'
import type { StaffUser } from '../../domain/entities/staff-user-schema'
import { usePushNotifications } from '../hooks/use-push-notifications'
import { useRefreshContext } from '../context/refresh-context'
import { NotificationBell } from './notification-bell/NotificationBell'
import { NavMenuButton } from './AppShell'
import { Avatar } from './ui/Avatar'

const NOW_TICK_INTERVAL_MS = 30_000

function formatRelativeTime(date: Date, now: Date): string {
  const diffSeconds = Math.max(0, Math.round((now.getTime() - date.getTime()) / 1000))
  if (diffSeconds < 5) return 'just now'
  if (diffSeconds < 60) return `${diffSeconds}s ago`
  const diffMinutes = Math.round(diffSeconds / 60)
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.round(diffMinutes / 60)
  return `${diffHours}h ago`
}

// Shared manual-refresh control for whichever operational list/dashboard
// page is currently active (see live-data-refresh's modified requirement).
// Reads its target from RefreshContext instead of owning any fetch itself -
// each page's own data hook is what actually knows how to refresh itself.
function RefreshControl() {
  const { activeRefresh } = useRefreshContext()
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    if (!activeRefresh) return
    const intervalId = setInterval(() => setNow(new Date()), NOW_TICK_INTERVAL_MS)
    return () => clearInterval(intervalId)
  }, [activeRefresh])

  if (!activeRefresh) return null

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={activeRefresh.refresh}
        aria-label="Refresh"
        className="flex size-10 items-center justify-center rounded-full border border-border bg-surface text-text lg:size-8"
      >
        <RefreshCcwIcon className={`size-3.5 ${activeRefresh.isRefreshing ? 'animate-spin' : ''}`} />
      </button>
      {activeRefresh.lastUpdatedAt && (
        <span className="hidden font-body text-[11px] whitespace-nowrap text-text-faint md:inline">
          Updated {formatRelativeTime(activeRefresh.lastUpdatedAt, now)}
        </span>
      )}
    </div>
  )
}

export interface AppTopBarBreadcrumbItem {
  label: string
  isActive?: boolean
}

interface AppTopBarProps {
  // Section name shown on md+, e.g. "Organization Admin" or "Reception Desk".
  title: string
  description?: string
  breadcrumb?: AppTopBarBreadcrumbItem[]
  currentUser: StaffUser | undefined
  // The current page's own nav label, shown instead of `title` on phones.
  navLabelFor: (pathname: string) => string
  loginPath: string
}

// The persistent top bar shared by the admin and staff shells, so the two
// sections' chrome can't drift apart.
export function AppTopBar({ title, description, breadcrumb, currentUser, navLabelFor, loginPath }: AppTopBarProps) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { unregisterCurrentDevice } = usePushNotifications()

  const signOut = () => {
    void unregisterCurrentDevice().finally(() => {
      sessionStorage.removeItem('token')
      navigate(loginPath)
    })
  }

  return (
    <header className="flex h-16 w-full shrink-0 items-center justify-between gap-3 border-b border-border bg-surface px-4 md:h-[70px] md:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <NavMenuButton />
        {breadcrumb ? (
          <div className="flex min-w-0 items-center gap-1 overflow-hidden font-body text-xs whitespace-nowrap">
            {breadcrumb.map((item, index) => (
              // On phone only the active crumb shows, so the trail can't
              // push the controls off the right edge.
              <span key={item.label} className={`min-w-0 items-center gap-1 ${item.isActive ? 'flex' : 'hidden md:flex'}`}>
                {index > 0 && <span className="hidden text-text-faint md:inline">{'>'}</span>}
                <span className={`truncate font-medium ${item.isActive ? 'font-semibold text-admin-accent' : 'text-text-faint'}`}>{item.label}</span>
              </span>
            ))}
          </div>
        ) : (
          <div className="flex min-w-0 flex-col gap-0.5">
            {/* Below md the page's own name (from the section's nav), not a
                generic label that truncates to "Organizat…". */}
            <p className="truncate font-display text-lg font-bold text-text md:hidden">{navLabelFor(pathname)}</p>
            <p className="hidden truncate font-display text-xl font-bold text-text md:block">{title}</p>
            <p className="hidden truncate font-body text-[13px] text-text-faint md:block">{description}</p>
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2 md:gap-6">
        <RefreshControl />
        <NotificationBell />

        <div className="flex items-center gap-2">
          <Avatar name={currentUser?.name ?? ''} size="md" />
          <div className="hidden flex-col gap-0.5 md:flex">
            <p className="font-body text-[13px] font-semibold text-text">{currentUser?.name ?? '—'}</p>
            <p className="font-body text-[11px] text-text-faint">{currentUser?.role ?? ''}</p>
          </div>
        </div>

        <div className="hidden h-6 w-px bg-border md:block" />

        <button
          type="button"
          onClick={signOut}
          aria-label="Sign out"
          className="flex min-h-10 min-w-10 items-center justify-center gap-1.5 rounded-lg px-2 py-2 font-body text-[13px] font-semibold text-text-muted md:px-3"
        >
          <LogOutIcon className="size-4 md:size-3.5" />
          <span className="hidden md:inline">Sign out</span>
        </button>
      </div>
    </header>
  )
}
