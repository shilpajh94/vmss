import { useEffect, type RefObject } from 'react'

// Calls `onReach` when `sentinelRef` scrolls within `rootMarginPx` of the
// bottom of `rootRef`'s scroll area. `watchKey` should change whenever the
// list grows: the observer is recreated, and a fresh observer reports the
// sentinel's current state - so a page too short to fill the column keeps
// loading until it does, instead of stalling because "still intersecting"
// never fires a second callback.
//
// `rootRef` is only used as the observer root while it actually scrolls
// (desktop, where each column is height-bounded). Below `lg` the column grows
// with its content and the page scrolls instead; observing against a root
// that never clips would report the sentinel as always visible and load
// every page at once, so the viewport is used there.
export function useInfiniteScrollSentinel(
  sentinelRef: RefObject<HTMLElement | null>,
  rootRef: RefObject<HTMLElement | null>,
  onReach: () => void,
  { enabled, watchKey, rootMarginPx = 200 }: { enabled: boolean; watchKey: unknown; rootMarginPx?: number },
) {
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!enabled || !sentinel || typeof IntersectionObserver === 'undefined') return

    const scrollArea = rootRef.current
    const root = scrollArea && scrollArea.scrollHeight > scrollArea.clientHeight ? scrollArea : null
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) onReach()
      },
      { root, rootMargin: `0px 0px ${rootMarginPx}px 0px` },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [sentinelRef, rootRef, onReach, enabled, watchKey, rootMarginPx])
}
