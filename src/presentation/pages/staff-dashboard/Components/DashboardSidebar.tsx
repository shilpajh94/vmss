import { CheckIcon, ClockIcon, HelpCircleIcon, ShieldIcon, UsersIcon } from './icons'

const NAV_ITEMS = [
  { label: 'All visitors', icon: UsersIcon, active: true },
  { label: 'My actions', icon: CheckIcon, active: false },
  { label: 'Audit trail', icon: ClockIcon, active: false },
] as const

export function DashboardSidebar() {
  return (
    <aside className="flex w-[260px] shrink-0 flex-col gap-8 self-stretch bg-primary p-6">
      <div className="flex items-center gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-secondary-accent">
          <ShieldIcon className="size-[18px] text-white" />
        </span>
        <span className="font-display text-xl font-extrabold whitespace-nowrap text-white">VisitorPass</span>
      </div>

      <nav className="flex flex-col gap-2">
        {NAV_ITEMS.map(({ label, icon: ItemIcon, active }) => (
          <button
            key={label}
            type="button"
            className={`flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left font-body text-sm font-semibold ${
              active ? 'bg-[#1e293b] text-[#f1f5f9]' : 'text-[#cbd5e1] hover:bg-[#1e293b]/60'
            }`}
          >
            <ItemIcon className="size-[18px] shrink-0" />
            {label}
          </button>
        ))}
      </nav>

      <div className="flex flex-1 flex-col justify-end gap-4">
        <div className="h-px w-full bg-[#1e293b]" />
        <button type="button" className="flex w-full items-center gap-2 rounded-lg bg-[#1e293b] px-3 py-2 text-left">
          <HelpCircleIcon className="size-4 text-secondary-accent" />
          <span className="font-body text-[13px] font-semibold whitespace-nowrap text-secondary-accent">Help &amp; Support</span>
        </button>
      </div>
    </aside>
  )
}
