import { useCallback, useState } from 'react'

function readStored<T>(key: string, fallback: T, parse: (raw: unknown) => T | undefined): T {
  try {
    const raw = window.localStorage.getItem(key)
    if (raw === null) return fallback
    return parse(JSON.parse(raw)) ?? fallback
  } catch {
    return fallback
  }
}

// A per-browser UI preference (declutter-invitation-board design.md
// Decision 1). Read in the lazy initializer so the stored value is on the
// first render - no expand-then-collapse flicker. Storage can be blocked
// (private window, site-data policy) or hold a stale shape, so every access
// is guarded and `parse` rejects anything unexpected; the state still works
// in memory either way.
export function useStoredState<T>(
  key: string,
  fallback: T,
  parse: (raw: unknown) => T | undefined,
): [T, (update: T | ((previous: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => readStored(key, fallback, parse))

  const setStoredValue = useCallback(
    (update: T | ((previous: T) => T)) => {
      setValue((previous) => {
        const next = typeof update === 'function' ? (update as (previous: T) => T)(previous) : update
        try {
          window.localStorage.setItem(key, JSON.stringify(next))
        } catch {
          // Storage unavailable - keep the in-memory value only.
        }
        return next
      })
    },
    [key],
  )

  return [value, setStoredValue]
}
