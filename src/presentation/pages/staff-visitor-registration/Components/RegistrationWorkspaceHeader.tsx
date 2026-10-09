import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { LogOutIcon } from '../../../components/icons'
import { NotificationBell } from '../../../components/notification-bell/NotificationBell'
import { initialsFor } from '../../../utils/initials'

interface RegistrationWorkspaceHeaderProps {
  currentUser: StaffUser | undefined
  onSignOut: () => void
}

export function RegistrationWorkspaceHeader({ currentUser, onSignOut }: RegistrationWorkspaceHeaderProps) {
  return (
    <div className="flex w-full flex-wrap items-center justify-between gap-4 border-b border-border pb-4 md:pb-5">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-2xl font-extrabold text-text md:text-[28px]">Register Visitor</h1>
        <p className="font-body text-sm text-text-muted">Create a single or group pass entry request for your organization</p>
      </div>

      <div className="flex items-center gap-2 md:gap-4">
        <NotificationBell />

        {currentUser && (
          <div className="flex items-center gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full border-[1.5px] border-info bg-info/8 font-display text-[13px] font-bold text-info">
              {initialsFor(currentUser.name)}
            </span>
            <div className="hidden flex-col gap-0.5 whitespace-nowrap md:flex">
              <p className="font-body text-[13px] font-bold text-text">{currentUser.name}</p>
              <p className="font-body text-[11px] font-medium text-text-muted">{currentUser.role}</p>
            </div>
          </div>
        )}

        <div className="hidden h-6 w-px bg-border md:block" />

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
