import { useCallback, useEffect, useRef, useState } from 'react'
import { usePresence } from '../../hooks/use-presence'
import { PendingButton } from '../ui/PendingButton'
import { useNavigate } from 'react-router'
import { BellIcon } from '../icons'
import { useNotificationCenter } from '../../context/notification-center-context'
import { getPushState, usePushNotifications, type PushState } from '../../hooks/use-push-notifications'
import { buildInvitationPath } from '../../utils/notification-links'
import type { NotificationFeedItem } from '../../../domain/entities/notification-feed-schema'

// While anything is unread, the bell rings again this long after its last
// ring (app-shell "The notification bell repeats its ring while
// notifications stay unread").
const UNREAD_REMINDER_INTERVAL_MS = 15_000

function formatRelativeTime(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

interface NotificationRowProps {
  item: NotificationFeedItem
  onSelect: () => void
}

// Distinguishes a notification sent to every holder of a role from one
// delegated to this viewer personally (role-based-invitation-workflow) — read
// from the stored item's `data.reason`, so the badge survives a reload.
function AddressingBadge({ reason }: { reason: string | undefined }) {
  if (reason === 'role_assigned') {
    return (
      <span className="inline-flex shrink-0 items-center rounded-full bg-info/10 px-1.5 py-0.5 font-body text-[10px] font-semibold whitespace-nowrap text-info">
        Role
      </span>
    )
  }
  if (reason === 'delegated') {
    return (
      <span className="inline-flex shrink-0 items-center rounded-full bg-secondary-accent/10 px-1.5 py-0.5 font-body text-[10px] font-semibold whitespace-nowrap text-secondary-accent">
        Delegated to you
      </span>
    )
  }
  return null
}

function NotificationRow({ item, onSelect }: NotificationRowProps) {
  const isRead = item.readAt !== null
  return (
    <button type="button" onClick={onSelect} className="flex w-full items-start gap-2 px-4 py-2.5 text-left hover:bg-border-subtle">
      {!isRead && <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-admin-accent" />}
      <span className={`min-w-0 flex-1 ${isRead ? 'pl-3.5' : ''}`}>
        <span className="flex items-center gap-1.5">
          <span className="min-w-0 flex-1 truncate font-body text-[13px] font-semibold text-text">{item.title}</span>
          <AddressingBadge reason={item.data.reason} />
        </span>
        <span className="block truncate font-body text-[13px] text-text-muted">{item.body}</span>
        <span className="block font-body text-[11px] text-text-faint">{formatRelativeTime(item.createdAt)}</span>
      </span>
    </button>
  )
}

function pushStateMessage(state: PushState): string {
  switch (state.status) {
    case 'enabled':
      return 'Push notifications are on for this browser.'
    case 'off':
      return 'Push notifications are off for this browser.'
    case 'blocked':
      return "Push notifications are blocked. Allow notifications for this site in your browser's site settings, then reload the page."
    case 'unavailable':
      return state.reason === 'insecure-context'
        ? 'Push notifications need HTTPS or localhost, so they are unavailable here.'
        : "This browser doesn't support push notifications."
  }
}

// fix-web-push-and-add-notification-feed: makes the browser's push state
// visible, and is the only place that asks for notification permission —
// from the button's click, which browsers require.
function PushStatusRow() {
  const { enablePush } = usePushNotifications()
  const [pushState, setPushState] = useState<PushState>(getPushState)
  const [isEnabling, setIsEnabling] = useState(false)

  const handleEnable = () => {
    setIsEnabling(true)
    void enablePush()
      .then(setPushState)
      .finally(() => setIsEnabling(false))
  }

  return (
    <div className="border-t border-border bg-border-subtle/50 px-4 py-3">
      <p className="font-body text-[12px] text-text-muted">{pushStateMessage(pushState)}</p>
      {pushState.status !== 'enabled' && (
        <p className="mt-1 font-body text-[12px] text-text-faint">You'll still see new notifications here.</p>
      )}
      {pushState.status === 'off' && (
        <PendingButton
          onClick={handleEnable}
          pending={isEnabling}
          pendingLabel="Enabling…"
          className="mt-2 rounded-md bg-admin-accent px-3 py-1.5 font-body text-[12px] font-semibold text-on-accent disabled:opacity-60"
        >
          Enable notifications
        </PendingButton>
      )}
    </div>
  )
}

export function NotificationBell() {
  const { notifications, unreadCount, markRead, markAllRead, newArrivalCount, panelOpenRequest } = useNotificationCenter()
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  // Fades/scales out from the bell before unmounting (ui-motion "Popovers
  // and menus animate from their anchor").
  const popover = usePresence(isOpen)

  // Every ring - a new arrival or a reminder - bumps this key, which
  // remounts the icon wrapper and replays the ring animation.
  const [ringKey, setRingKey] = useState(0)
  const lastRingAtRef = useRef(Date.now())

  // The one place a ring starts: with nothing unread the bell never
  // animates, whatever asked for the ring (app-shell "The notification bell
  // rings when a new notification arrives"). Reads the latest count through
  // a ref so both the effect and the timeout below see the current value.
  const unreadCountRef = useRef(unreadCount)
  unreadCountRef.current = unreadCount
  const ring = useCallback(() => {
    if (unreadCountRef.current > 0) setRingKey((previous) => previous + 1)
  }, [])
  const [isTabVisible, setIsTabVisible] = useState(() => document.visibilityState === 'visible')

  // Ring only when the count moves after mount, so a bell remounted later
  // in the session doesn't replay an arrival it already rang for.
  const seenArrivalCountRef = useRef(newArrivalCount)
  useEffect(() => {
    if (newArrivalCount === seenArrivalCountRef.current) return
    seenArrivalCountRef.current = newArrivalCount
    ring()
  }, [newArrivalCount, ring])

  useEffect(() => {
    lastRingAtRef.current = Date.now()
  }, [ringKey])

  useEffect(() => {
    const updateVisibility = () => setIsTabVisible(document.visibilityState === 'visible')
    document.addEventListener('visibilitychange', updateVisibility)
    return () => document.removeEventListener('visibilitychange', updateVisibility)
  }, [])

  // Re-armed after every ring; measured from the last ring so a changing
  // count doesn't postpone it. Nothing is scheduled while all is read, the
  // popover is open, or the tab is hidden.
  useEffect(() => {
    if (unreadCount === 0 || isOpen || !isTabVisible) return
    const delay = Math.max(0, lastRingAtRef.current + UNREAD_REMINDER_INTERVAL_MS - Date.now())
    const timeoutId = window.setTimeout(ring, delay)
    return () => window.clearTimeout(timeoutId)
  }, [ringKey, unreadCount, isOpen, isTabVisible, ring])

  // Open on request from elsewhere (a grouped push summary toast); like
  // the ring, only requests made after mount count.
  const seenPanelOpenRequestRef = useRef(panelOpenRequest)
  useEffect(() => {
    if (panelOpenRequest === seenPanelOpenRequestRef.current) return
    seenPanelOpenRequestRef.current = panelOpenRequest
    setIsOpen(true)
  }, [panelOpenRequest])

  useEffect(() => {
    if (!isOpen) return

    const handlePointerDown = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [isOpen])

  const selectNotification = (item: NotificationFeedItem) => {
    markRead(item.id)
    setIsOpen(false)
    const invitationId = item.data.invitationId
    if (invitationId) navigate(buildInvitationPath(invitationId))
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((previous) => !previous)}
        aria-label={`Notifications, ${unreadCount} unread`}
        aria-expanded={isOpen}
        className="relative flex size-10 items-center justify-center rounded-full bg-border-subtle transition-colors duration-fast hover:bg-border lg:size-9"
      >
        {/* Keyed by the ring count so each ring remounts it and replays the
            animation; no class before the first ring, so loading the page
            never rings. */}
        <span key={ringKey} className={ringKey > 0 ? 'motion-bell-ring' : 'inline-flex'}>
          <BellIcon className="size-4 text-text" />
        </span>
        {/* Exact count, always shown; anchored by its left edge so extra
            digits grow outward instead of across the icon. */}
        <span
          aria-hidden
          className={`absolute -top-0.5 left-[55%] flex h-4 min-w-4 items-center justify-center rounded-full px-1 font-body text-[10px] leading-none font-semibold tabular-nums ${
            unreadCount > 0 ? 'bg-danger text-on-accent' : 'bg-border text-text-muted'
          }`}
        >
          {unreadCount}
        </span>
      </button>

      {popover.isMounted && (
        <div
          data-state={popover.state}
          inert={popover.state === 'closing'}
          onAnimationEnd={popover.onAnimationEnd}
          className="motion-popover fixed inset-x-2 top-16 z-50 flex max-h-[70dvh] origin-top flex-col rounded-lg border border-border bg-surface shadow-[0_8px_24px_rgba(15,23,42,0.12)] md:absolute md:inset-x-auto md:top-11 md:right-0 md:max-h-[460px] md:w-[340px] md:origin-top-right"
        >
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <p className="font-body text-[13px] font-semibold text-text">Notifications</p>
            {unreadCount > 0 && (
              <button type="button" onClick={markAllRead} className="font-body text-[12px] font-semibold text-admin-accent hover:underline">
                Mark all read
              </button>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="px-4 py-6 text-center font-body text-[13px] text-text-faint">No notifications yet.</p>
            ) : (
              <div className="divide-y divide-border">
                {notifications.map((item) => (
                  <NotificationRow key={item.id} item={item} onSelect={() => selectNotification(item)} />
                ))}
              </div>
            )}
          </div>
          <PushStatusRow />
        </div>
      )}
    </div>
  )
}
