// Helpers for a native <input type="datetime-local"> (YYYY-MM-DDTHH:mm, no
// zone, browser-local) against the API's ISO-8601 datetimes, which must carry
// an explicit offset (e.g. 2026-10-22T14:30:00+05:30).
function pad(value: number): string {
  return String(value).padStart(2, '0')
}

export function toDateTimeInputValue(iso?: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function nowAsDateTimeInputValue(): string {
  return toDateTimeInputValue(new Date().toISOString())
}

// Local datetime-local value -> ISO-8601 with the browser's UTC offset.
export function dateTimeInputToOffsetIso(value: string): string {
  const date = new Date(value)
  const offsetMinutes = -date.getTimezoneOffset()
  const sign = offsetMinutes >= 0 ? '+' : '-'
  const abs = Math.abs(offsetMinutes)
  return `${value}:00${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}

export function formatDateTimeInputValue(value: string): string {
  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
