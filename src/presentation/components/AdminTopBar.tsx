import { BellIcon, SearchGlyphIcon } from './icons'
import type { StaffUser } from '../../domain/entities/staff-user-schema'

interface AdminTopBarBreadcrumbItem {
  label: string
  isActive?: boolean
}

interface AdminTopBarProps {
  description?: string
  breadcrumb?: AdminTopBarBreadcrumbItem[]
  currentUser: StaffUser | undefined
}

export function AdminTopBar({ description, breadcrumb, currentUser }: AdminTopBarProps) {
  return (
    <header className="flex h-[70px] w-full shrink-0 items-center justify-between border-b border-border bg-surface px-8">
      {breadcrumb ? (
        <div className="flex items-center gap-1 font-body text-xs whitespace-nowrap">
          {breadcrumb.map((item, index) => (
            <span key={item.label} className="flex items-center gap-1">
              {index > 0 && <span className="text-text-faint">{'>'}</span>}
              <span className={`font-medium ${item.isActive ? 'font-semibold text-admin-accent' : 'text-text-faint'}`}>{item.label}</span>
            </span>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-0.5">
          <p className="font-display text-xl font-bold text-text">Organization Admin</p>
          <p className="font-body text-[13px] text-text-faint">{description}</p>
        </div>
      )}

      <div className="flex items-center gap-6">
        <div className="flex w-[260px] items-center gap-2 rounded-lg bg-border-subtle px-3 py-2">
          <SearchGlyphIcon className="size-4 shrink-0 text-text-faint" />
          <span className="font-body text-[13px] text-text-faint">Search workspace...</span>
        </div>

        <span className="relative flex size-9 items-center justify-center rounded-full bg-border-subtle">
          <BellIcon className="size-4 text-text" />
          <span className="absolute top-[10px] right-[10px] size-1.5 rounded-full bg-danger" />
        </span>

        <div className="flex items-center gap-2">
          <span className="size-8 rounded-full bg-neutral-subtle" />
          <div className="flex flex-col gap-0.5">
            <p className="font-body text-[13px] font-semibold text-text">{currentUser?.name ?? '—'}</p>
            <p className="font-body text-[11px] text-text-faint">{currentUser?.role ?? ''}</p>
          </div>
        </div>
      </div>
    </header>
  )
}
