import { useEffect, useRef, type RefObject } from 'react'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Active traps, innermost last. Only the innermost one handles keys, so a
// confirm dialog opened from inside another modal closes on Escape without
// also closing the modal underneath it.
const trapStack: object[] = []

// Keeps keyboard focus inside `containerRef` while `active`, calls `onEscape`
// on Escape, and hands focus back to whatever was focused before activation
// once it deactivates — the off-canvas nav drawer's and every Modal's
// accessibility contract (app-shell "Sidebar collapses into a drawer below
// desktop width"; ui-motion "Modal dialogs and sheets animate in and out").
export function useFocusTrap(containerRef: RefObject<HTMLElement | null>, active: boolean, onEscape: () => void) {
  // Read through a ref so callers can pass an inline callback: re-running
  // the effect on every render would re-focus the first control and steal
  // focus from whatever field the user is typing in.
  const onEscapeRef = useRef(onEscape)
  onEscapeRef.current = onEscape

  useEffect(() => {
    if (!active) return
    const container = containerRef.current
    if (!container) return
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const token = {}
    trapStack.push(token)

    const focusables = () => Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    // Respect a field that already took focus (autoFocus) on mount.
    if (!container.contains(document.activeElement)) focusables()[0]?.focus()

    const handleKeyDown = (event: KeyboardEvent) => {
      if (trapStack[trapStack.length - 1] !== token) return
      if (event.key === 'Escape') {
        event.preventDefault()
        onEscapeRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const items = focusables()
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      trapStack.splice(trapStack.indexOf(token), 1)
      previouslyFocused?.focus()
    }
  }, [active, containerRef])
}
