import { useMemo } from 'react'

// True when a form's current values differ from what it loaded (or started
// with), so the top-bar refresh can ask before discarding them
// (live-data-refresh "A manual refresh control remains available"). The
// forms this backs hold plain, JSON-serialisable values; a value typed and
// then reverted compares equal again.
export function useUnsavedChanges(initial: unknown, current: unknown): boolean {
  return useMemo(() => JSON.stringify(initial) !== JSON.stringify(current), [initial, current])
}
