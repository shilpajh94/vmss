// Pure keyboard/type-ahead logic for Select (modernise-dropdowns-and-sidebar-chrome
// design.md D3), kept out of the component so `node --test` can cover it.

export interface NavigableOption {
  label: string
  disabled?: boolean
}

// How long a pause in typing starts a fresh type-ahead search.
export const TYPEAHEAD_RESET_MS = 500

export function firstEnabled(options: readonly NavigableOption[]): number {
  return options.findIndex((option) => !option.disabled)
}

export function lastEnabled(options: readonly NavigableOption[]): number {
  for (let index = options.length - 1; index >= 0; index -= 1) {
    if (!options[index].disabled) return index
  }
  return -1
}

// Steps from `from` by `delta` (±1), skipping disabled options and clamping
// at the ends rather than wrapping, as native selects do. `from === -1`
// (nothing active yet) starts from the first or last enabled option.
export function nextEnabledIndex(options: readonly NavigableOption[], from: number, delta: 1 | -1): number {
  if (from < 0) return delta === 1 ? firstEnabled(options) : lastEnabled(options)
  for (let index = from + delta; index >= 0 && index < options.length; index += delta) {
    if (!options[index].disabled) return index
  }
  return from
}

export function initialActiveIndex(options: readonly (NavigableOption & { value: string })[], value: string): number {
  const selected = options.findIndex((option) => option.value === value && !option.disabled)
  return selected >= 0 ? selected : firstEnabled(options)
}

// The next enabled option whose label starts with `buffer`, searching after
// `from` and wrapping. A buffer of one repeated letter ("ww") cycles through
// the options starting with that letter, like a native select.
export function typeaheadMatch(options: readonly NavigableOption[], buffer: string, from: number): number {
  if (!buffer) return -1
  const lowered = buffer.toLowerCase()
  const isRepeat = lowered.length > 1 && [...lowered].every((char) => char === lowered[0])
  const needle = isRepeat ? lowered[0] : lowered
  // A multi-character search may still match the current option; a single
  // letter (or a repeat) moves past it.
  const start = needle.length > 1 ? Math.max(from, 0) : from + 1
  for (let offset = 0; offset < options.length; offset += 1) {
    const index = (start + offset + options.length) % options.length
    const option = options[index]
    if (!option.disabled && option.label.toLowerCase().startsWith(needle)) return index
  }
  return -1
}
