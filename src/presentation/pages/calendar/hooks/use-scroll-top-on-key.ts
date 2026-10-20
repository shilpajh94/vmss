import { useLayoutEffect, type RefObject } from 'react'

// Brings a day's scroller back to the top when its day, branch or status
// filter changes, so a list reset to its first page doesn't open scrolled
// near its end and load past that page straight away (staff-calendar
// "Status filter, truncation and empty states"; fix-e2e-suite-green
// design.md D2). A refresh keeps the same key, so it never moves the scroll.
// A layout effect, so the reset lands before the load-more sentinel is
// observed against the old position.
export function useScrollTopOnKey(ref: RefObject<HTMLElement | null>, key: string): void {
  useLayoutEffect(() => {
    if (ref.current) ref.current.scrollTop = 0
  }, [ref, key])
}
