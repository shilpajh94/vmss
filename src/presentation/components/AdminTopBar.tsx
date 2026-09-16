import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { LogOutIcon, RefreshCcwIcon } from './icons'
import type { StaffUser } from '../../domain/entities/staff-user-schema'
import { usePushNotifications } from '../hooks/use-push-notifications'
import { useRefreshContext } from '../context/refresh-context'
import { NotificationBell } from './notification-bell/NotificationBell'

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
        className="flex size-8 items-center justify-center rounded-full border border-border bg-surface text-text"
      >
        <RefreshCcwIcon className={`size-3.5 ${activeRefresh.isRefreshing ? 'animate-spin' : ''}`} />
      </button>
      {activeRefresh.lastUpdatedAt && (
        <span className="font-body text-[11px] whitespace-nowrap text-text-faint">
          Updated {formatRelativeTime(activeRefresh.lastUpdatedAt, now)}
        </span>
      )}
    </div>
  )
}

export interface AdminTopBarBreadcrumbItem {
  label: string
  isActive?: boolean
}

interface AdminTopBarProps {
  description?: string
  breadcrumb?: AdminTopBarBreadcrumbItem[]
  currentUser: StaffUser | undefined
}

export function AdminTopBar({ description, breadcrumb, currentUser }: AdminTopBarProps) {
  const navigate = useNavigate()
  const { unregisterCurrentDevice } = usePushNotifications()

  const signOut = () => {
    void unregisterCurrentDevice().finally(() => {
      sessionStorage.removeItem('token')
      navigate('/admin/login')
    })
  }

  return (
    <header className="flex h-[70px] w-full shrink-0 items-center justify-between border-b border-border bg-surface px-8">
      {breadcrumb ? (
        <div className="flex items-center gap-1 font-body text-xs whitespace-nowrap">
          {breadcrumb.map((item, index) => (
            <span key={item.label} className="flex items-center gap-1">
              {index > 0 && <span className="text-text-faint">{'>'}</span>}
              <span className={`font-medium ${item.isActive ? 'font-semibold text-admin-accent' : 'text-text-faint'}`}>{item.label}</span>
            </span>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-0.5">
          <p className="font-display text-xl font-bold text-text">Organization Admin</p>
          <p className="font-body text-[13px] text-text-faint">{description}</p>
        </div>
      )}

      <div className="flex items-center gap-6">
        <RefreshControl />
        <NotificationBell />

        <div className="flex items-center gap-2">
          <span className="size-8 rounded-full bg-neutral-subtle" />
          <div className="flex flex-col gap-0.5">
            <p className="font-body text-[13px] font-semibold text-text">{currentUser?.name ?? '—'}</p>
            <p className="font-body text-[11px] text-text-faint">{currentUser?.role ?? ''}</p>
          </div>
        </div>

        <div className="h-6 w-px bg-border" />

        <button
          type="button"
          onClick={signOut}
          aria-label="Sign out"
          className="flex items-center gap-1.5 rounded-lg px-3 py-2 font-body text-[13px] font-semibold text-text-muted"
        >
          <LogOutIcon className="size-3.5" />
          Sign out
        </button>
      </div>
    </header>
  )
}
