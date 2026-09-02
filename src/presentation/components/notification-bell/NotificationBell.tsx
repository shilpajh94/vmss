import { useEffect, useRef, useState } from 'react'
import { BellIcon } from '../icons'
import { useNotificationCenter, type NotificationCenterItem } from '../../context/notification-center-context'

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
  item: NotificationCenterItem
  onSelect: () => void
}

function NotificationRow({ item, onSelect }: NotificationRowProps) {
  const content = (
    <>
      {!item.read && <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-admin-accent" />}
      <span className={`min-w-0 flex-1 ${item.read ? 'pl-3.5' : ''}`}>
        <span className="block truncate font-body text-[13px] text-text">{item.message}</span>
        <span className="block font-body text-[11px] text-text-faint">{formatRelativeTime(item.receivedAt)}</span>
      </span>
    </>
  )

  if (!item.onClick) {
    return <div className="flex items-start gap-2 px-4 py-2.5">{content}</div>
  }

  return (
    <button type="button" onClick={onSelect} className="flex w-full items-start gap-2 px-4 py-2.5 text-left hover:bg-border-subtle">
      {content}
    </button>
  )
}

export function NotificationBell() {
  const { notifications, unreadCount, markAllRead } = useNotificationCenter()
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

  const toggleOpen = () => {
    if (!isOpen) markAllRead()
    setIsOpen((previous) => !previous)
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={toggleOpen}
        aria-label="Notifications"
        aria-expanded={isOpen}
        className="relative flex size-9 items-center justify-center rounded-full bg-border-subtle"
      >
        <BellIcon className="size-4 text-text" />
        {unreadCount > 0 && <span className="absolute top-[10px] right-[10px] size-1.5 rounded-full bg-danger" />}
      </button>

      {isOpen && (
        <div className="absolute top-11 right-0 z-50 max-h-[400px] w-[340px] overflow-y-auto rounded-lg border border-border bg-surface shadow-[0_8px_24px_rgba(15,23,42,0.12)]">
          <div className="border-b border-border px-4 py-3">
            <p className="font-body text-[13px] font-semibold text-text">Notifications</p>
          </div>
          {notifications.length === 0 ? (
            <p className="px-4 py-6 text-center font-body text-[13px] text-text-faint">No notifications yet.</p>
          ) : (
            <div className="divide-y divide-border">
              {notifications.map((item) => (
                <NotificationRow
                  key={item.id}
                  item={item}
                  onSelect={() => {
                    item.onClick?.()
                    setIsOpen(false)
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
