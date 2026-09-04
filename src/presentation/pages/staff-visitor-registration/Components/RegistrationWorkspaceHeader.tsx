import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { LogOutIcon } from '../../../components/icons'
import { NotificationBell } from '../../../components/notification-bell/NotificationBell'

interface RegistrationWorkspaceHeaderProps {
  currentUser: StaffUser | undefined
  onSignOut: () => void
}

function initialsFor(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

export function RegistrationWorkspaceHeader({ currentUser, onSignOut }: RegistrationWorkspaceHeaderProps) {
  return (
    <div className="flex w-full items-center justify-between border-b border-border px-10 py-5">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-[28px] font-extrabold text-text">Register Visitor</h1>
        <p className="font-body text-sm text-text-muted">Create a single or group pass entry request for your organization</p>
      </div>

      <div className="flex items-center gap-4">
        <NotificationBell />

        {currentUser && (
          <div className="flex items-center gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full border-[1.5px] border-info bg-info/8 font-display text-[13px] font-bold text-info">
              {initialsFor(currentUser.name)}
            </span>
            <div className="flex flex-col gap-0.5 whitespace-nowrap">
              <p className="font-body text-[13px] font-bold text-text">{currentUser.name}</p>
              <p className="font-body text-[11px] font-medium text-text-muted">{currentUser.role}</p>
            </div>
          </div>
        )}

        <div className="h-6 w-px bg-border" />

        <button type="button" onClick={onSignOut} className="flex items-center gap-1.5 rounded-lg px-3 py-2 font-body text-[13px] font-semibold text-text-muted">
          <LogOutIcon className="size-3.5" />
          Sign out
        </button>
      </div>
    </div>
  )
}
