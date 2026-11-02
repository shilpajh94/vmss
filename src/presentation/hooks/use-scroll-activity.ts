import { useEffect, type RefObject } from 'react'

// How long after the last scroll event the overlay thumb starts fading out.
const SCROLL_IDLE_MS = 800

export interface EdgeState {
  atTop: boolean
  atBottom: boolean
}

// 1px of slack absorbs fractional scroll positions on zoomed or high-DPI screens.
export function edgeState(scrollTop: number, clientHeight: number, scrollHeight: number): EdgeState {
  return {
    atTop: scrollTop <= 1,
    atBottom: scrollTop + clientHeight >= scrollHeight - 1,
  }
}

// Mirrors a scroll region's activity onto data attributes for CSS:
// `data-scrolling` while it is being scrolled (cleared SCROLL_IDLE_MS after
// the last scroll), `data-at-top` / `data-at-bottom` at either end. The
// sidebar nav's auto-hiding thumb and edge fades key off these
// (modernise-dropdowns-and-sidebar-chrome design.md D7). Attributes are set
// directly, so scrolling never re-renders the sidebar.
export function useScrollActivity(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const element = ref.current
    if (!element) return
    let idleTimeoutId = 0

    const syncEdges = () => {
      const { atTop, atBottom } = edgeState(element.scrollTop, element.clientHeight, element.scrollHeight)
      element.toggleAttribute('data-at-top', atTop)
      element.toggleAttribute('data-at-bottom', atBottom)
    }

    const onScroll = () => {
      syncEdges()
      element.setAttribute('data-scrolling', '')
      window.clearTimeout(idleTimeoutId)
      idleTimeoutId = window.setTimeout(() => element.removeAttribute('data-scrolling'), SCROLL_IDLE_MS)
    }

    syncEdges()
    element.addEventListener('scroll', onScroll, { passive: true })
    // The list grows when permission-gated items arrive and shrinks/grows
    // with the viewport; either can move the list's ends.
    const resizeObserver = new ResizeObserver(syncEdges)
    resizeObserver.observe(element)
    for (const child of Array.from(element.children)) resizeObserver.observe(child)
    const mutationObserver = new MutationObserver(syncEdges)
    mutationObserver.observe(element, { childList: true, subtree: true })

    return () => {
      window.clearTimeout(idleTimeoutId)
      element.removeEventListener('scroll', onScroll)
      resizeObserver.disconnect()
      mutationObserver.disconnect()
    }
  }, [ref])
}
