import { useCallback, useEffect, useState, type AnimationEvent } from 'react'
import { MOTION_MS } from '../utils/motion'

export type PresenceState = 'open' | 'closing'

// Grace period on top of the exit duration before the fallback unmount,
// so it never cuts a still-running animation short.
const FALLBACK_SLACK_MS = 50

// Keeps an overlay mounted through its exit animation (ui-motion: overlays
// "SHALL be removed only after the exit animation ends"). Render the
// element while `isMounted`, set `data-state={state}` on it, and attach
// `onAnimationEnd` to the element whose closing animation is the one to
// wait for. CSS keyframes keyed on `[data-state]` (index.css) do the
// motion; this hook only decides when the node may leave the DOM.
//
// `animationend` is the primary signal; a timeout is the fallback, so an
// element whose animation never runs (display: none, an interrupted
// animation) can't be stranded as an invisible overlay. Under
// prefers-reduced-motion the CSS shortens animations to ~0ms, and
// `animationend` still fires, so no special case is needed here.
export function usePresence(isOpen: boolean, exitMs: number = MOTION_MS.standard) {
  const [isMounted, setIsMounted] = useState(isOpen)
  const [state, setState] = useState<PresenceState>('open')

  // Adjusting state from a prop change during render (React's documented
  // pattern) rather than in an effect, so the first open frame already
  // has the element mounted and the closing state lands in the same
  // render as the prop flip - no one-frame flash of the old state.
  if (isOpen && (!isMounted || state !== 'open')) {
    setIsMounted(true)
    setState('open')
  } else if (!isOpen && isMounted && state !== 'closing') {
    setState('closing')
  }

  useEffect(() => {
    if (!isMounted || state !== 'closing') return
    const timeoutId = setTimeout(() => setIsMounted(false), exitMs + FALLBACK_SLACK_MS)
    return () => clearTimeout(timeoutId)
  }, [isMounted, state, exitMs])

  const onAnimationEnd = useCallback(
    (event: AnimationEvent<HTMLElement>) => {
      // Animation events bubble; ignore ones from descendants (spinners,
      // skeletons, nested popovers).
      if (event.target !== event.currentTarget) return
      if (state === 'closing') setIsMounted(false)
    },
    [state],
  )

  return { isMounted, state, onAnimationEnd }
}
