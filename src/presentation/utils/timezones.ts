// The organisation's default timezone is an IANA zone name, the form the API
// resolves first (design D-W8). Values saved before that were `GMT±HH:MM`
// strings; `toIanaTimezone` upgrades one to a zone with the same offset today,
// preferring the curated zones below so `GMT+05:30` becomes `Asia/Kolkata`.

const PREFERRED_ZONES = [
  'Asia/Kolkata',
  'Asia/Dubai',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
  'Europe/London',
  'Europe/Paris',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'UTC',
]

const LEGACY_OFFSET = /^GMT([+-])(\d{2}):(\d{2})$/

export interface TimezoneOption {
  value: string
  label: string
}

// ICU (Node, and Chromium until recently) still lists some zones under
// their pre-rename names. Show the current name, which is what the API and
// other browsers store.
const RENAMED_ZONES: Record<string, string> = {
  'Africa/Asmera': 'Africa/Asmara',
  'America/Godthab': 'America/Nuuk',
  'Asia/Calcutta': 'Asia/Kolkata',
  'Asia/Katmandu': 'Asia/Kathmandu',
  'Asia/Rangoon': 'Asia/Yangon',
  'Asia/Saigon': 'Asia/Ho_Chi_Minh',
  'Atlantic/Faeroe': 'Atlantic/Faroe',
  'Europe/Kiev': 'Europe/Kyiv',
  'Pacific/Enderbury': 'Pacific/Kanton',
  'Pacific/Ponape': 'Pacific/Pohnpei',
  'Pacific/Truk': 'Pacific/Chuuk',
}

function supportedZones(): string[] {
  const zones = Intl.supportedValuesOf('timeZone').map((zone) => RENAMED_ZONES[zone] ?? zone)
  return [...new Set([...zones, 'UTC'])]
}

/** Today's UTC offset of `zone` in minutes, e.g. 330 for Asia/Kolkata. */
function offsetMinutes(zone: string, at: Date): number {
  const name = new Intl.DateTimeFormat('en-US', { timeZone: zone, timeZoneName: 'longOffset' })
    .formatToParts(at)
    .find((part) => part.type === 'timeZoneName')?.value
  const match = name?.match(/^GMT([+-])(\d{2}):(\d{2})$/)
  if (!match) return 0
  const minutes = Number(match[2]) * 60 + Number(match[3])
  return match[1] === '-' ? -minutes : minutes
}

function formatOffset(minutes: number): string {
  const sign = minutes < 0 ? '-' : '+'
  const absolute = Math.abs(minutes)
  return `GMT${sign}${String(Math.floor(absolute / 60)).padStart(2, '0')}:${String(absolute % 60).padStart(2, '0')}`
}

/**
 * Every supported zone, ordered by offset, labelled `(GMT+05:30) Asia/Kolkata`.
 * `current` is always included, so a stored zone this browser doesn't list
 * still shows as selected.
 */
export function timezoneOptions(current?: string, at: Date = new Date()): TimezoneOption[] {
  const zones = supportedZones()
  const options = zones
    .map((zone) => ({ zone, offset: offsetMinutes(zone, at) }))
    .sort((a, b) => a.offset - b.offset || a.zone.localeCompare(b.zone))
    .map(({ zone, offset }) => ({ value: zone, label: `(${formatOffset(offset)}) ${zone.replace(/_/g, ' ')}` }))
  return current && !zones.includes(current) ? [{ value: current, label: current }, ...options] : options
}

/** Upgrades a legacy `GMT±HH:MM` value; any other value is returned as is. */
export function toIanaTimezone(value: string, at: Date = new Date()): string {
  const match = value.match(LEGACY_OFFSET)
  if (!match) return value
  const minutes = (Number(match[2]) * 60 + Number(match[3])) * (match[1] === '-' ? -1 : 1)
  const candidates = [...PREFERRED_ZONES, ...supportedZones()]
  return candidates.find((zone) => offsetMinutes(zone, at) === minutes) ?? value
}
