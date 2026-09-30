// Class strings for the admin list tables' phone/tablet behavior
// (responsive-layout "Data Tables Scroll Within Their Container and Keep
// Actions Reachable"; make-web-pages-responsive design.md Decision 4).
// Applied to the <table> element itself, so no individual <th>/<td> needs
// editing: a column is hidden below `md` by its 1-based position, in the
// header and body alike. Kept as whole literals (not built by
// concatenation) so Tailwind's scanner generates every one of them.

// Tighter cell padding below `md`, and the last (actions) column pinned to
// the right edge of the scroll container on every width. Below `md` the
// first (identifying) column may wrap instead of forcing the table wider
// than the screen, and the pinned column carries a divider and shadow so
// it never reads as covering the status cell beside it
// (fix-layout-spacing-and-footer-logo design.md Decision 3).
export const RESPONSIVE_TABLE_CLASS =
  'w-full text-left max-md:[&_:is(th,td)]:px-4 max-md:[&_tbody_td:first-child]:whitespace-normal max-md:[&_tbody_td:first-child]:min-w-[8rem] [&_tr>*:last-child]:sticky [&_tr>*:last-child]:right-0 [&_tr>*:last-child]:border-l [&_tr>*:last-child]:border-border [&_tbody_tr>*:last-child]:bg-surface [&_tbody_tr>*:last-child]:shadow-[-8px_0_8px_-8px_rgba(15,23,42,0.15)] [&_thead_tr>*:last-child]:bg-border-subtle'

export const HIDE_BELOW_MD_COLUMN = {
  2: 'max-md:[&_tr>*:nth-child(2)]:hidden',
  3: 'max-md:[&_tr>*:nth-child(3)]:hidden',
  4: 'max-md:[&_tr>*:nth-child(4)]:hidden',
  5: 'max-md:[&_tr>*:nth-child(5)]:hidden',
  6: 'max-md:[&_tr>*:nth-child(6)]:hidden',
  7: 'max-md:[&_tr>*:nth-child(7)]:hidden',
} as const

export function responsiveTableClassName(hiddenBelowMd: ReadonlyArray<keyof typeof HIDE_BELOW_MD_COLUMN>): string {
  return [RESPONSIVE_TABLE_CLASS, ...hiddenBelowMd.map((column) => HIDE_BELOW_MD_COLUMN[column])].join(' ')
}
