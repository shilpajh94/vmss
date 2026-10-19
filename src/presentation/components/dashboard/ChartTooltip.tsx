export interface ChartTooltipRow {
  label: string
  value: number
  color?: string
}

// Tooltip body shared by the Recharts charts: text stays in text ink, and a
// small swatch beside each value carries the series identity.
export function ChartTooltipContent({ title, rows }: { title: string; rows: ChartTooltipRow[] }) {
  return (
    <div className="flex min-w-[150px] flex-col gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 shadow-lg">
      <p className="font-body text-xs font-semibold text-text">{title}</p>
      {rows.map((row) => (
        <div key={row.label} className="flex items-center justify-between gap-4 font-body text-xs">
          <span className="flex items-center gap-1.5 text-text-muted">
            {row.color ? <span className="size-2 rounded-full" style={{ backgroundColor: row.color }} /> : null}
            {row.label}
          </span>
          <span className="font-semibold text-text tabular-nums">{row.value}</span>
        </div>
      ))}
    </div>
  )
}
