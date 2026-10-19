import { useEffect, useRef, useState, type RefObject } from 'react'

// One turn per this long at full speed.
const TURN_MS = 800
const DEGREES_PER_MS = 360 / TURN_MS
// Ease-in ramp up to full speed. easeInQuad leaves at twice its average
// speed, so covering RAMP_DEGREES in RAMP_MS exits at exactly
// DEGREES_PER_MS - no hitch where the loop takes over.
const RAMP_MS = 300
const RAMP_DEGREES = (DEGREES_PER_MS * RAMP_MS) / 2
const EASE_IN_QUAD = 'cubic-bezier(0.11, 0, 0.5, 0)'
// The settle runs on at full speed, then eases out over the last stretch.
// easeOutQuad also starts at twice its average speed, so the tail takes
// 2 * SETTLE_TAIL_DEGREES / DEGREES_PER_MS - 180ms beyond finishing the turn
// at full speed, one standard motion step (ui-motion "The refresh control's
// icon accelerates, spins and settles").
const SETTLE_TAIL_DEGREES = 81
const EASE_OUT_QUAD = 'cubic-bezier(0.5, 1, 0.89, 1)'

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

// The element's current clockwise rotation in [0, 360), read from its
// computed transform (a matrix, mid-animation).
function currentAngle(element: Element): number {
  const transform = getComputedStyle(element).transform
  if (!transform || transform === 'none') return 0
  const { a, b } = new DOMMatrixReadOnly(transform)
  return ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360
}

function rotate(degrees: number): Keyframe {
  return { transform: `rotate(${degrees}deg)` }
}

// Drives the top-bar refresh icon (`isSpinning` = a user-started refresh is
// in flight): eases in, spins steadily, and on stop finishes its turn and
// eases out to rest upright instead of snapping back. Starting again while
// it settles carries on from the current angle.
//
// Returns true when the caller should fall back to a plain constant spin
// (`animate-spin`, which the global reduced-motion rule keeps running)
// while `isSpinning`: under reduced motion, which also drops the easing.
export function useRefreshSpin(targetRef: RefObject<HTMLElement | null>, isSpinning: boolean): boolean {
  const animationRef = useRef<Animation | null>(null)
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(() => window.matchMedia(REDUCED_MOTION_QUERY).matches)

  useEffect(() => {
    const query = window.matchMedia(REDUCED_MOTION_QUERY)
    const update = () => setPrefersReducedMotion(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    const element = targetRef.current
    if (!element) return

    if (prefersReducedMotion) {
      animationRef.current?.cancel()
      animationRef.current = null
      return
    }

    const previous = animationRef.current
    const wasMoving = previous !== null && previous.playState === 'running'
    const fromAngle = previous ? currentAngle(element) : 0

    if (isSpinning) {
      const startLoop = (loopFromAngle: number) => {
        const loop = element.animate([rotate(loopFromAngle), rotate(loopFromAngle + 360)], {
          duration: TURN_MS,
          iterations: Infinity,
          easing: 'linear',
        })
        animationRef.current?.cancel()
        animationRef.current = loop
      }

      // Already turning (caught mid-settle): carry straight on at speed.
      if (wasMoving) {
        startLoop(fromAngle)
        return
      }

      const ramp = element.animate([rotate(fromAngle), rotate(fromAngle + RAMP_DEGREES)], {
        duration: RAMP_MS,
        easing: EASE_IN_QUAD,
        fill: 'forwards',
      })
      previous?.cancel()
      animationRef.current = ramp
      ramp.onfinish = () => {
        if (animationRef.current === ramp) startLoop(fromAngle + RAMP_DEGREES)
      }
      return
    }

    // Stopped: nothing to settle if it never moved.
    if (!previous) return

    const remaining = 360 - fromAngle
    const tail = Math.min(remaining, SETTLE_TAIL_DEGREES)
    const cruiseMs = (remaining - tail) / DEGREES_PER_MS
    const tailMs = (2 * tail) / DEGREES_PER_MS
    const settle = element.animate(
      [
        { ...rotate(fromAngle), offset: 0, easing: 'linear' },
        { ...rotate(360 - tail), offset: cruiseMs / (cruiseMs + tailMs), easing: EASE_OUT_QUAD },
        { ...rotate(360), offset: 1 },
      ],
      { duration: cruiseMs + tailMs, fill: 'forwards' },
    )
    previous.cancel()
    animationRef.current = settle
    settle.onfinish = () => {
      if (animationRef.current !== settle) return
      // 360° and 0° look the same; dropping the fill leaves it at rest.
      settle.cancel()
      animationRef.current = null
    }
  }, [targetRef, isSpinning, prefersReducedMotion])

  useEffect(
    () => () => {
      animationRef.current?.cancel()
    },
    [],
  )

  return prefersReducedMotion
}
