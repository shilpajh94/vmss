import { Link } from 'react-router'

export interface BarListItem {
  key: string
  label: string
  value: number
  // A Tailwind background class for the bar (e.g. a board status colour).
  barClassName: string
  href?: string
}

// Labeled horizontal bars: the name and count are text, so identity never
// rests on the bar colour. Bars scale to the largest value; rows with an
// `href` are links.
export function BarList({ items, valueLabel }: { items: BarListItem[]; valueLabel: string }) {
  const max = Math.max(1, ...items.map((item) => item.value))

  return (
    <ul className="flex flex-col gap-1">
      {items.map((item) => {
        const content = (
          <>
            <div className="flex items-center justify-between gap-3 font-body text-sm">
              <span className="min-w-0 truncate text-text-muted">{item.label}</span>
              <span className="shrink-0 font-semibold text-text tabular-nums">{item.value}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-border-subtle">
              <div className={`h-full rounded-full ${item.barClassName}`} style={{ width: `${(item.value / max) * 100}%` }} />
            </div>
          </>
        )

        return (
          <li key={item.key}>
            {item.href ? (
              <Link
                to={item.href}
                aria-label={`${item.label}: ${item.value} ${valueLabel}. View these invitations`}
                className="flex min-h-11 flex-col justify-center gap-1.5 rounded-lg px-2 py-1.5 hover:bg-border-subtle focus-visible:outline-2 focus-visible:outline-admin-accent"
              >
                {content}
              </Link>
            ) : (
              <div className="flex min-h-11 flex-col justify-center gap-1.5 px-2 py-1.5">{content}</div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
