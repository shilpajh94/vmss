const TIME_FORMATTER = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' })
const DATE_FORMATTER = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' })

export function formatTime(iso: string | null): string {
  if (!iso) return '—'

  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'

  return TIME_FORMATTER.format(date)
}

export function formatDate(iso: string | null): string {
  if (!iso) return '—'

  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'

  return DATE_FORMATTER.format(date)
}
