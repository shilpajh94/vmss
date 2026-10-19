// JS mirror of theme.css's --motion-* durations, for code that has to know
// how long an animation lasts (use-presence's unmount fallback). Change
// both together.
export const MOTION_MS = {
  fast: 100,
  standard: 180,
  slow: 280,
} as const
