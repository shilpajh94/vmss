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
    // Below `lg` the stacked header (title, full-width search and filters) can
    // be taller than the phone's viewport, so the whole page scrolls as one
    // instead of squeezing the data region to a sliver.
    <div className="flex flex-col gap-4 md:gap-6 lg:h-full lg:min-h-0">
      <div className="flex flex-none flex-col gap-4 md:gap-6">{header}</div>
      <div className="lg:min-h-0 lg:flex-1 lg:overflow-y-auto">{children}</div>
    </div>
  )
}
