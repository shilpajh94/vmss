import { useLayoutEffect, useRef, useState, type RefObject } from 'react'

interface FillHeightOptions {
  /** Smallest height in px. */
  floor: number
  /** Off: the element sizes to its content and this returns undefined. */
  enabled: boolean
}

// Sizes a calendar panel (the Week board, the Day card) to the visible page
// area: the shell's scrolling <main> less its top padding and the page's
// bottom gap (which equals <main>'s side padding, app-shell "Page content
// keeps a bottom gap"), but never below `floor`. The title and toolbar above
// the panel scroll away with the page, so scrolled down, the panel fills the
// screen while its own body keeps scrolling on its own (staff-calendar "Week
// board and Day card are as tall as the visible page";
// calendar-page-scroll-and-taller-panels design.md D1).
//
// The panel's own top isn't part of the sum, so a wrapping toolbar or a
// notice above it doesn't change its height, only the page's scroll length.
// An explicit height overflows in order, so the shell's end-gap spacer
// still follows the panel.
//
// Observing <main> itself is safe: only its border box is watched, and the
// panel's height doesn't change that. It catches <main> resizing without a
// window resize (e.g. the top bar changing height).
export function useFillHeight<T extends HTMLElement>({ floor, enabled }: FillHeightOptions): [RefObject<T | null>, number | undefined] {
  const ref = useRef<T>(null)
  const [height, setHeight] = useState(floor)

  useLayoutEffect(() => {
    if (!enabled) return
    const scroller = ref.current?.closest('main') ?? null
    const measure = () => {
      if (!scroller) {
        setHeight(Math.max(floor, window.innerHeight))
        return
      }
      const style = getComputedStyle(scroller)
      const top = parseFloat(style.paddingTop) || 0
      const gap = parseFloat(style.paddingLeft) || 0
      setHeight(Math.max(floor, Math.floor(scroller.clientHeight - top - gap)))
    }
    measure()
    const observer = new ResizeObserver(measure)
    if (scroller) observer.observe(scroller)
    window.addEventListener('resize', measure)
    window.addEventListener('orientationchange', measure)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measure)
      window.removeEventListener('orientationchange', measure)
    }
  }, [enabled, floor])

  return [ref, enabled ? height : undefined]
}
