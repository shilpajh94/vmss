import type { ReactNode } from 'react'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { LogOutIcon, RefreshCcwIcon } from '../../../components/icons'
import { NotificationBell } from '../../../components/notification-bell/NotificationBell'
import { Avatar } from '../../../components/ui/Avatar'

interface WorkspaceHeaderProps {
  currentUser: StaffUser | undefined
  onRefresh: () => void
  onSignOut: () => void
  /** Rendered first in the right-hand group, before Refresh (e.g. Reception's Export). */
  leadingAction?: ReactNode
}

export function WorkspaceHeader({ currentUser, onRefresh, onSignOut, leadingAction }: WorkspaceHeaderProps) {
  return (
    <div className="flex w-full flex-wrap items-center justify-between gap-4">
      <div className="flex flex-col gap-0.5">
        <h1 className="font-display text-xl font-extrabold text-text md:text-2xl">Visits</h1>
        <p className="font-body text-[13px] text-text-muted">All visit requests for your organisation</p>
      </div>

      <div className="flex items-center gap-2 md:gap-4">
        {leadingAction}
        <button
          type="button"
          onClick={onRefresh}
          className="flex min-h-10 items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 font-body text-[13px] font-semibold text-text md:px-4"
        >
          <RefreshCcwIcon className="size-3.5" />
          Refresh
        </button>

        <div className="hidden h-6 w-px bg-border md:block" />

        <NotificationBell />

        {currentUser && (
          <div className="flex items-center gap-3">
            <Avatar name={currentUser.name} size="lg" />
            <div className="hidden flex-col gap-0.5 whitespace-nowrap md:flex">
              <p className="font-body text-[13px] font-bold text-text">{currentUser.name}</p>
              <p className="font-body text-[11px] font-medium text-text-muted">{currentUser.role}</p>
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={onSignOut}
          aria-label="Sign out"
          className="flex min-h-10 min-w-10 items-center justify-center gap-1.5 rounded-lg px-2 py-2 font-body text-[13px] font-semibold text-text-muted md:px-3"
        >
          <LogOutIcon className="size-4 md:size-3.5" />
          <span className="hidden md:inline">Sign out</span>
        </button>
      </div>
    </div>
  )
}
