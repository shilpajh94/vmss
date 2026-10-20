import type { ReactNode, Ref } from 'react'

// Cancels the header column's own gap (gap-4 md:gap-6 below) for a closed
// Collapsible filter panel, so the closed panel takes no space at all.
export const PAGE_HEADER_GAP_CANCEL = '-mt-4 md:-mt-6'

interface PageContentLayoutProps {
  /** Heading, Filters/Add row, and (when open) the filter panel - stays fixed. */
  header: ReactNode
  /** Table, board, or list - the only region that scrolls. */
  children: ReactNode
  /**
   * Optional action bar pinned below the scrolling region (e.g. a wizard's
   * Cancel/Next). Rendered as a direct child of the layout root, unwrapped, so
   * a `sticky` footer can stick against the whole page below `lg` - give it
   * `flex-none` so it never shrinks from `lg` up.
   */
  footer?: ReactNode
  /** Ref to the layout root, e.g. to scroll it into view below `lg`. */
  rootRef?: Ref<HTMLDivElement>
  /** Ref to the scrolling region, e.g. to reset its scroll position. */
  bodyRef?: Ref<HTMLDivElement>
  /** Extra classes for the scrolling region. */
  bodyClassName?: string
  /**
   * Size the data region to its content (shrinking and scrolling only once
   * it outgrows the page) instead of filling the height, so a footer such
   * as pagination sits right under a short list rather than at the window
   * bottom. Off by default: boards and wizards fill the height.
   */
  fitBody?: boolean
}

// Keeps a page's own heading/Filters/Add row (and its filter panel, when
// open) fixed in place while only the data region beneath it scrolls - one
// level deeper than AppShell's existing sidebar/top-bar-fixed behavior. An
// optional footer (a wizard's action bar, a list's pagination) stays pinned
// below that region the same way. Relies on
// RouteTransition's wrapper stretching to fill <main>'s available height
// (see RouteTransition.tsx), and flexes into what's left of it rather than
// taking its full height, so the wrapper's trailing end-gap spacer still
// fits below; a page that doesn't use this layout is unaffected, since only
// this component's own data region gets overflow.
export function PageContentLayout({ header, children, footer, rootRef, bodyRef, bodyClassName = '', fitBody = false }: PageContentLayoutProps) {
  // `flex-initial` is flex 0 1 auto: as tall as its content, but still
  // shrinks (min-h-0) and scrolls when the content outgrows the page.
  const bodySizing = fitBody ? 'lg:flex-initial' : 'lg:flex-1'
  return (
    // Below `lg` the stacked header (title, full-width search and filters) can
    // be taller than the phone's viewport, so the whole page scrolls as one
    // instead of squeezing the data region to a sliver.
    <div ref={rootRef} className="flex flex-col gap-4 md:gap-6 lg:min-h-0 lg:flex-1">
      <div className="flex flex-none flex-col gap-4 md:gap-6">{header}</div>
      <div ref={bodyRef} className={`lg:min-h-0 ${bodySizing} lg:overflow-y-auto ${bodyClassName}`.trimEnd()}>
        {children}
      </div>
      {footer}
    </div>
  )
}
