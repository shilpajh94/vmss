import { useNavigate } from 'react-router'
import { LogOutIcon } from '../../../components/icons'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { usePushNotifications } from '../../../hooks/use-push-notifications'
import { NotificationBell } from '../../../components/notification-bell/NotificationBell'
import { NavMenuButton } from '../../../components/AppShell'
import { Avatar } from '../../../components/ui/Avatar'

interface ReceptionTopBarProps {
  description?: string
  currentUser: StaffUser | undefined
}

export function ReceptionTopBar({ description, currentUser }: ReceptionTopBarProps) {
  const navigate = useNavigate()
  const { unregisterCurrentDevice } = usePushNotifications()

  const signOut = () => {
    void unregisterCurrentDevice().finally(() => {
      sessionStorage.removeItem('token')
      navigate('/staff/login')
    })
  }

  return (
    <header className="flex h-16 w-full shrink-0 items-center justify-between gap-3 border-b border-border bg-surface px-4 md:h-[70px] md:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <NavMenuButton />
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="truncate font-display text-lg font-bold text-text md:text-xl">Reception Desk</p>
          <p className="hidden truncate font-body text-[13px] text-text-faint md:block">{description}</p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 md:gap-6">
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
