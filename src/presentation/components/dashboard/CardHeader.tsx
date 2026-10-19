import { Link } from 'react-router'
import { ChevronRightIcon } from '../icons'

// Title row for a dashboard list card, with its "View all" link to the board.
export function CardHeader({ title, subtitle, viewAllHref, viewAllLabel }: { title: string; subtitle?: string; viewAllHref: string; viewAllLabel: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <h2 className="font-display text-lg font-bold text-text">{title}</h2>
        {subtitle ? <p className="font-body text-sm text-text-faint">{subtitle}</p> : null}
      </div>
      <Link
        to={viewAllHref}
        aria-label={viewAllLabel}
        className="flex min-h-10 shrink-0 items-center gap-0.5 rounded-lg px-2 font-body text-sm font-semibold text-admin-accent hover:bg-admin-accent/10"
      >
        View all
        <ChevronRightIcon className="size-4" />
      </Link>
    </div>
  )
}
