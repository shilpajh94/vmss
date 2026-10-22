import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { LogOutIcon, RefreshCcwIcon } from './icons'
import type { StaffUser } from '../../domain/entities/staff-user-schema'
import { usePushNotifications } from '../hooks/use-push-notifications'
import { useRefreshContext } from '../context/refresh-context'
import { useAppDependencies } from '../context/app-dependencies-context'
import { NotificationBell } from './notification-bell/NotificationBell'
import { ThemeModeMenu } from './ThemeModeMenu'
import { NavMenuButton } from './AppShell'
import { Avatar } from './ui/Avatar'
import { useRefreshSpin } from '../hooks/use-refresh-spin'
import { ConfirmDialog } from './ui/ConfirmDialog'

// A manual refresh that never reports progress stops spinning after this.
const MANUAL_REFRESH_SPIN_LIMIT_MS = 15_000

// How long sign-out waits for the server before clearing the session anyway.
const SIGN_OUT_TIMEOUT_MS = 4000

function formatClockTime(date: Date): string {
  return [date.getHours(), date.getMinutes(), date.getSeconds()].map((part) => String(part).padStart(2, '0')).join(':')
}

// Device-local 24-hour HH:MM:SS (app-shell "The top bar shows a live
// clock"). Its own component so only it re-renders each second; ticks are
// aligned to whole seconds so it stays in step with the device clock.
// tabular-nums keeps its width fixed; no aria-live, so screen readers
// aren't sent every tick.
function TopBarClock() {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    let intervalId: number | undefined
    const timeoutId = window.setTimeout(() => {
      setNow(new Date())
      intervalId = window.setInterval(() => setNow(new Date()), 1000)
    }, 1000 - (Date.now() % 1000))
    return () => {
      window.clearTimeout(timeoutId)
      window.clearInterval(intervalId)
    }
  }, [])

  return (
    <time dateTime={now.toISOString()} className="hidden font-body text-[13px] font-semibold text-text-muted tabular-nums md:inline">
      {formatClockTime(now)}
    </time>
  )
}

// Shared manual-refresh control for whichever operational list/dashboard
// page is currently active (see live-data-refresh's modified requirement).
// Reads its target from RefreshContext instead of owning any fetch itself -
// each page's own data hook is what actually knows how to refresh itself.
// Always present: RefreshProvider falls back to a shell refresh. A form page
// with unsaved edits gets a discard confirmation first.
//
// The icon spins only for a refresh the user started: from the click until
// the page's isRefreshing has risen and fallen again. Background polls move
// isRefreshing too, but with no click pending they're ignored. The spin
// eases in and settles upright (useRefreshSpin); the inner wrapper carries
// the idle hover nudge separately so the two transforms never fight.
function RefreshControl() {
  const { activeRefresh } = useRefreshContext()
  const [isConfirmingDiscard, setIsConfirmingDiscard] = useState(false)
  const [isManualRefreshPending, setIsManualRefreshPending] = useState(false)
  const sawRefreshingRef = useRef(false)
  const spinRef = useRef<HTMLSpanElement>(null)
  const isConstantSpin = useRefreshSpin(spinRef, isManualRefreshPending)

  useEffect(() => {
    if (!isManualRefreshPending) return
    if (activeRefresh.isRefreshing) sawRefreshingRef.current = true
    else if (sawRefreshingRef.current) setIsManualRefreshPending(false)
  }, [isManualRefreshPending, activeRefresh.isRefreshing])

  useEffect(() => {
    if (!isManualRefreshPending) return
    const timeoutId = window.setTimeout(() => setIsManualRefreshPending(false), MANUAL_REFRESH_SPIN_LIMIT_MS)
    return () => window.clearTimeout(timeoutId)
  }, [isManualRefreshPending])

  const startRefresh = () => {
    sawRefreshingRef.current = false
    setIsManualRefreshPending(true)
    activeRefresh.refresh()
  }

  const requestRefresh = () => {
    if (activeRefresh.hasUnsavedChanges) setIsConfirmingDiscard(true)
    else startRefresh()
  }

  return (
    <div className="flex items-center gap-2">
      <ConfirmDialog
        isOpen={isConfirmingDiscard}
        title="Discard unsaved changes?"
        message="Refreshing reloads this page's saved data. The changes you haven't saved will be lost."
        confirmLabel="Discard and refresh"
        onConfirm={() => {
          setIsConfirmingDiscard(false)
          startRefresh()
        }}
        onCancel={() => setIsConfirmingDiscard(false)}
      />
      <button
        type="button"
        onClick={requestRefresh}
        aria-label={activeRefresh.hasFailed ? "Refresh (last refresh failed, retrying)" : 'Refresh'}
        className={`refresh-control flex size-10 items-center justify-center rounded-full border bg-surface text-text lg:size-8 ${
          activeRefresh.hasFailed ? 'border-warning' : 'border-border'
        }`}
      >
        <span ref={spinRef} data-refresh-spin className={`inline-flex ${isConstantSpin && isManualRefreshPending ? 'animate-spin' : ''}`}>
          <span data-spinning={isManualRefreshPending || undefined} className="refresh-nudge inline-flex">
            <RefreshCcwIcon className="size-3.5" />
          </span>
        </span>
      </button>
      {activeRefresh.hasFailed && (
        <span role="status" className="hidden font-body text-[11px] whitespace-nowrap text-warning md:inline">
          Couldn't refresh · retrying
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
  const { logoutStaffUseCase } = useAppDependencies()

  // Both calls need the token, so they run before it is cleared. Neither
  // failing (or hanging) can keep the user signed in (app-shell "Signing
  // Out Ends the Server Session").
  const signOut = () => {
    const serverSignOut = Promise.allSettled([logoutStaffUseCase.execute(), unregisterCurrentDevice()])
    const timeout = new Promise((resolve) => window.setTimeout(resolve, SIGN_OUT_TIMEOUT_MS))
    void Promise.race([serverSignOut, timeout]).finally(() => {
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
        <TopBarClock />
        <RefreshControl />
        <ThemeModeMenu />
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
