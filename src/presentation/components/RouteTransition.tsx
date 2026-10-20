import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { useLocation } from 'react-router'

interface RouteTransitionProps {
  children: ReactNode
  withEndGap?: boolean
}

// Plays a brief fade/slide-in on route change instead of an instant
// content swap. Keying the wrapper on the pathname forces React to remount
// it on every navigation, which restarts the CSS animation defined for
// `.route-transition` in index.css (that stylesheet also disables it under
// `prefers-reduced-motion: reduce`). CSS-only by design — no animation
// library — so only the entering view animates; there is no exit animation.
//
// `flex h-full min-h-0 flex-col` makes this wrapper stretch to fill
// <main>'s available height (which is itself a definite, not auto, height -
// see AppShell.tsx) instead of sizing to its content. A page that renders
// short content just leaves empty space below it, same as before. A page
// that renders tall content and does NOT opt into PageContentLayout still
// overflows this box normally, so <main>'s own overflow-y-auto keeps
// scrolling it exactly as before. A page that DOES use PageContentLayout
// gets a data region that scrolls internally instead, since it never
// exceeds this wrapper's height in the first place.
//
// `gap-page-section` lives here, not only on <main>: this wrapper is
// <main>'s only child, so a page that returns a fragment of sections would
// otherwise render them touching (fix-layout-spacing-and-footer-logo
// design.md Decision 1). A single-root page has one child, so it's a no-op.
//
// `withEndGap` (the staff and admin shells) ends the content with a spacer
// that makes the page's bottom gap. <main> has no bottom padding: a page
// taller than this fixed-height wrapper overflows it, and a scroller's end
// padding doesn't follow overflow, so it would sit behind the content.
// The spacer overflows along with the page, so the gap is always at the end
// of the scroll (app-shell "Page content keeps a bottom gap"). It must never
// be zero-height, or it drops out of the scrollable area (see h-page-end-gap).
//
// Every navigation also starts the new page at the top (app-shell "Scroll
// position resets on navigation"): the shells' scrolling <main>, or the
// window on the public pages that scroll as a whole. A layout effect, so
// the reset lands before the first paint of the incoming page.
export function RouteTransition({ children, withEndGap = false }: RouteTransitionProps) {
  const location = useLocation()
  const wrapperRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const scrollContainer = wrapperRef.current?.closest('main')
    if (scrollContainer) scrollContainer.scrollTo({ top: 0 })
    else window.scrollTo({ top: 0 })
  }, [location.pathname])

  return (
    <div ref={wrapperRef} key={location.pathname} className="route-transition flex h-full min-h-0 flex-col gap-page-section">
      {children}
      {withEndGap ? <div aria-hidden className="h-page-end-gap flex-none" /> : null}
    </div>
  )
}
