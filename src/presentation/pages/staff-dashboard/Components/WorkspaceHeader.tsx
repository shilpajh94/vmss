import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { LogOutIcon, RefreshCcwIcon } from '../../../components/icons'

interface WorkspaceHeaderProps {
  currentUser: StaffUser | undefined
  onRefresh: () => void
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

export function WorkspaceHeader({ currentUser, onRefresh, onSignOut }: WorkspaceHeaderProps) {
  return (
    <div className="flex w-full items-center justify-between">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-[28px] font-extrabold text-text">Visits</h1>
        <p className="font-body text-sm text-text-muted">All visit requests for your organisation</p>
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onRefresh}
          className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
        >
          <RefreshCcwIcon className="size-3.5" />
          Refresh
        </button>

        <div className="h-6 w-px bg-border" />

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

        <button type="button" onClick={onSignOut} className="flex items-center gap-1.5 rounded-lg px-3 py-2 font-body text-[13px] font-semibold text-text-muted">
          <LogOutIcon className="size-3.5" />
          Sign out
        </button>
      </div>
    </div>
  )
}
