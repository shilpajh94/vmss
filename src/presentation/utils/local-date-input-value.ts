// "Today" as a native <input type="date"> value (YYYY-MM-DD) in the browser's
// local timezone — `toISOString()` shifts by the UTC offset and can report
// the wrong day near midnight.
export function todayAsDateInputValue(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
