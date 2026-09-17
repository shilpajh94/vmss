import type { ReactNode } from 'react'

interface PageContentLayoutProps {
  /** Heading, Filters/Add row, and (when open) the filter panel - stays fixed. */
  header: ReactNode
  /** Table, board, or list - the only region that scrolls. */
  children: ReactNode
}

// Keeps a list page's own heading/Filters/Add row (and its filter panel,
// when open) fixed in place while only the data region beneath it scrolls -
// one level deeper than AppShell's existing sidebar/top-bar-fixed behavior.
// Relies on RouteTransition's wrapper stretching to fill <main>'s available
// height (see RouteTransition.tsx); a page that doesn't use this layout is
// unaffected, since only this component's own data region gets overflow.
export function PageContentLayout({ header, children }: PageContentLayoutProps) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-6">
      <div className="flex flex-none flex-col gap-6">{header}</div>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </div>
  )
}
