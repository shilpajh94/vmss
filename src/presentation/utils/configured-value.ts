// These are baked in at build time from the pipeline's variable library. A
// variable missing from the library reaches the build as its literal
// `$(NAME)` reference, so anything that isn't a real https URL or address
// counts as unset and its link is hidden rather than broken.
export function configuredUrl(value: string | undefined): string | null {
  const trimmed = value?.trim()
  if (!trimmed) return null
  try {
    return new URL(trimmed).protocol === 'https:' ? trimmed : null
  } catch {
    return null
  }
}

export function configuredEmail(value: string | undefined): string | null {
  const trimmed = value?.trim()
  return trimmed && /^[^\s@()$]+@[^\s@()$]+\.[^\s@()$]+$/.test(trimmed) ? trimmed : null
}
