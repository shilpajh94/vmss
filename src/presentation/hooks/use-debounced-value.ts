import { useEffect, useState } from 'react'

// Delays reflecting a fast-changing value (e.g. a search input) until it
// has stopped changing for `delayMs`, so a server-bound filter doesn't turn
// every keystroke into a request.
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timeoutId = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timeoutId)
  }, [value, delayMs])

  return debounced
}
