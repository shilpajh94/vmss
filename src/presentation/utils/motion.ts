// theme.css's --motion-* durations, read from the CSS custom properties so
// the two can't drift, for code that has to know how long an animation lasts
// (use-presence's unmount fallback, the toast removal fallback). The numbers
// below are only used where there is no stylesheet (unit tests, SSR) or a
// value can't be parsed.
const FALLBACK_MS = {
  fast: 100,
  standard: 180,
  slow: 280,
} as const

type MotionSpeed = keyof typeof FALLBACK_MS

// The tokens don't change at runtime, so each is read (with a style
// recalculation) once, the first time it is asked for with a stylesheet.
const cache: Partial<Record<MotionSpeed, number>> = {}

function readMotionMs(speed: MotionSpeed): number {
  const cached = cache[speed]
  if (cached !== undefined) return cached
  if (typeof document === 'undefined') return FALLBACK_MS[speed]
  const raw = getComputedStyle(document.documentElement).getPropertyValue(`--motion-${speed}`).trim()
  const value = Number.parseFloat(raw)
  if (!Number.isFinite(value)) return FALLBACK_MS[speed]
  const ms = raw.endsWith('ms') ? value : raw.endsWith('s') ? value * 1000 : FALLBACK_MS[speed]
  cache[speed] = ms
  return ms
}

export const MOTION_MS: Readonly<Record<MotionSpeed, number>> = {
  get fast() {
    return readMotionMs('fast')
  },
  get standard() {
    return readMotionMs('standard')
  },
  get slow() {
    return readMotionMs('slow')
  },
}
