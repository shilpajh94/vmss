import { ProgressBar } from '../ui/ProgressBar'
import type { ReactNode } from 'react'
import { EmptyState } from '../ui/EmptyState'

export interface ChartTableColumn {
  key: string
  label: string
}

interface ChartCardProps {
  title: string
  subtitle?: string
  // Header controls, e.g. a range toggle or a "View all" link.
  actions?: ReactNode
  // Spoken summary of what the chart shows (dashboard-insights "Charts Have
  // Accessible Summaries and Empty States").
  summary: string
  isEmpty: boolean
  emptyMessage: string
  // The same rows as the chart, as a table only assistive technology sees.
  // The chart itself stays exposed: its keyboard tooltips and any links in it
  // must remain reachable.
  table?: { columns: ChartTableColumn[]; rows: Record<string, string | number>[] }
  // Dims the chart while a new range is loading, keeping the old data visible.
  isUpdating?: boolean
  className?: string
  children: ReactNode
}

export function ChartCard({ title, subtitle, actions, summary, isEmpty, emptyMessage, table, isUpdating = false, className = '', children }: ChartCardProps) {
  return (
    <section
      aria-label={title}
      aria-busy={isUpdating}
      className={`relative flex min-w-0 flex-col gap-4 overflow-hidden rounded-2xl border border-border bg-surface p-4 md:p-6 ${className}`}
    >
      {/* Range change in flight: the chart stays, dimmed, under a progress
          bar along the card's top edge (async-ui-states "Changing a
          dashboard date range"). Absolutely placed so it takes no space. */}
      <div className="absolute inset-x-0 top-0">
        <ProgressBar isActive={isUpdating} className="rounded-none" />
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 className="font-display text-lg font-bold text-text">{title}</h2>
          {subtitle ? <p className="font-body text-sm text-text-faint">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </div>

      {isEmpty ? (
        <EmptyState message={emptyMessage} className="min-h-[180px] py-8" />
      ) : (
        // `relative` anchors the sr-only table; without a positioned ancestor
        // its absolute box escapes <main>'s clipping and widens the page.
        <figure aria-label={summary} className={`relative m-0 min-w-0 transition-opacity duration-standard ${isUpdating ? 'opacity-60' : ''}`}>
          {children}
          {table ? (
            // sr-only on a wrapper: a <table> ignores the 1px width and would
            // still size itself to its content.
            <div className="sr-only">
            <table>
              <caption>{summary}</caption>
              <thead>
                <tr>
                  {table.columns.map((column) => (
                    <th key={column.key} scope="col">
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, index) => (
                  <tr key={index}>
                    {table.columns.map((column) => (
                      <td key={column.key}>{row[column.key]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          ) : null}
        </figure>
      )}
    </section>
  )
}
