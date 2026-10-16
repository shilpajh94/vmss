import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { BellIcon } from '../icons'
import { useNotificationCenter } from '../../context/notification-center-context'
import { getPushState, usePushNotifications, type PushState } from '../../hooks/use-push-notifications'
import { buildInvitationPath } from '../../utils/notification-links'
import type { NotificationFeedItem } from '../../../domain/entities/notification-feed-schema'

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
        <button
          type="button"
          onClick={handleEnable}
          disabled={isEnabling}
          className="mt-2 rounded-md bg-admin-accent px-3 py-1.5 font-body text-[12px] font-semibold text-white disabled:opacity-60"
        >
          {isEnabling ? 'Enabling…' : 'Enable notifications'}
        </button>
      )}
    </div>
  )
}

export function NotificationBell() {
  const { notifications, unreadCount, markRead, markAllRead } = useNotificationCenter()
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

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

  const badgeLabel = unreadCount > 9 ? '9+' : String(unreadCount)

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((previous) => !previous)}
        aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
        aria-expanded={isOpen}
        className="relative flex size-10 items-center justify-center rounded-full bg-border-subtle lg:size-9"
      >
        <BellIcon className="size-4 text-text" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 font-body text-[10px] leading-none font-semibold text-white">
            {badgeLabel}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="fixed inset-x-2 top-16 z-50 flex max-h-[70dvh] flex-col rounded-lg border border-border bg-surface shadow-[0_8px_24px_rgba(15,23,42,0.12)] md:absolute md:inset-x-auto md:top-11 md:right-0 md:max-h-[460px] md:w-[340px]">
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
