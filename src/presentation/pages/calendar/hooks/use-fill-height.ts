import { useLayoutEffect, useRef, useState, type RefObject } from 'react'

interface FillHeightOptions {
  /** Smallest height in px; below it the page scrolls instead. */
  floor: number
  /** Off: the element sizes to its content and this returns undefined. */
  enabled: boolean
  /**
   * The block above the element (page header and toolbar). Its size changes
   * when it wraps, e.g. when the branch selector appears or the sidebar
   * collapses, which moves the element's top.
   */
  observeRef: RefObject<HTMLElement | null>
  /** Anything else above the element that comes and goes, e.g. an empty-week notice. */
  remeasureKey?: unknown
}

// Sizes a calendar panel (the Week board, the Day card) to the space left
// in the shell's scrolling <main> below its own top, minus the page's
// bottom gap (which equals <main>'s side padding, app-shell "Page content
// keeps a bottom gap"), but never below `floor`.
//
// Measured rather than flexed: a floor on a flex item inside a `min-h-0`
// parent overflows that parent and strands the shell's end-gap spacer
// above it, while an explicit height overflows in order, so a window too
// short for the floor just scrolls <main> with the gap still after the
// panel (fix-paging-footers-and-calendar-day-scroll design.md D3).
//
// <main>'s own content is deliberately not observed: the panel's height
// changes it, which would loop. Error states replace the whole panel, so
// nothing else is inserted above it.
export function useFillHeight<T extends HTMLElement>({
  floor,
  enabled,
  observeRef,
  remeasureKey,
}: FillHeightOptions): [RefObject<T | null>, number | undefined] {
  const ref = useRef<T>(null)
  const [height, setHeight] = useState(floor)

  useLayoutEffect(() => {
    if (!enabled) return
    const measure = () => {
      const element = ref.current
      if (!element) return
      const scroller = element.closest('main')
      const scrollerTop = scroller?.getBoundingClientRect().top ?? 0
      const top = element.getBoundingClientRect().top + (scroller?.scrollTop ?? 0) - scrollerTop
      const gap = scroller ? parseFloat(getComputedStyle(scroller).paddingLeft) || 0 : 0
      const visible = (scroller?.clientHeight ?? window.innerHeight) - top - gap
      setHeight(Math.max(floor, Math.floor(visible)))
    }
    measure()
    const observer = new ResizeObserver(measure)
    if (observeRef.current) observer.observe(observeRef.current)
    window.addEventListener('resize', measure)
    window.addEventListener('orientationchange', measure)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measure)
      window.removeEventListener('orientationchange', measure)
    }
  }, [enabled, floor, observeRef, remeasureKey])

  return [ref, enabled ? height : undefined]
}
