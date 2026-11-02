import { formatDayLabel } from '../dashboard/dashboard-format'
import type { InvitationDrillDown } from '../../../data/repositories/visit-request-summary-repository'
import { STATUS_OPTIONS } from './filter-options'

// The dashboard drill-down a board was opened with (dashboard-insights "Every
// Dashboard Figure Matches the List It Opens"). The board sends these on
// every column request and on export, and shows each one as a removable chip.
export type BoardDrillDownKey = keyof InvitationDrillDown

const DATE = /^\d{4}-\d{2}-\d{2}$/
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function validDate(value: string | null): string | undefined {
  if (!value || !DATE.test(value)) return undefined
  return Number.isNaN(Date.parse(value)) ? undefined : value
}

// Known statuses from every repeated `status` param, in URL order; unknown
// ones are dropped, as before.
export function parseDeepLinkStatuses(searchParams: URLSearchParams): string[] {
  const known = new Set(STATUS_OPTIONS.map((option) => option.value))
  return [...new Set(searchParams.getAll('status').filter((value) => known.has(value)))]
}

// Malformed values are ignored, never an error.
export function parseDrillDown(searchParams: URLSearchParams): InvitationDrillDown {
  const drillDown: InvitationDrillDown = {}
  const visitDateFrom = validDate(searchParams.get('visitDateFrom'))
  const visitDateTo = validDate(searchParams.get('visitDateTo'))
  if (visitDateFrom) drillDown.visitDateFrom = visitDateFrom
  if (visitDateTo && (!visitDateFrom || visitDateTo >= visitDateFrom)) drillDown.visitDateTo = visitDateTo
  if (searchParams.get('upcoming') === 'true') drillDown.upcoming = true
  if (searchParams.get('excludeExpired') === 'true') drillDown.excludeExpired = true
  const branchId = searchParams.get('branchId')
  if (branchId && UUID.test(branchId)) drillDown.branchId = branchId
  return drillDown
}

export interface DrillDownChip {
  // The params the chip stands for; removing it drops all of them.
  keys: BoardDrillDownKey[]
  label: string
}

function visitDateLabel(from: string | undefined, to: string | undefined): string {
  if (from && to) return from === to ? formatDayLabel(from) : `${formatDayLabel(from)} – ${formatDayLabel(to)}`
  if (from) return `from ${formatDayLabel(from)}`
  return `until ${formatDayLabel(to as string)}`
}

export function drillDownChips(drillDown: InvitationDrillDown, branchName: string | undefined): DrillDownChip[] {
  const chips: DrillDownChip[] = []
  if (drillDown.visitDateFrom || drillDown.visitDateTo) {
    chips.push({ keys: ['visitDateFrom', 'visitDateTo'], label: `Visit date: ${visitDateLabel(drillDown.visitDateFrom, drillDown.visitDateTo)}` })
  }
  if (drillDown.upcoming) chips.push({ keys: ['upcoming'], label: 'Upcoming only' })
  if (drillDown.excludeExpired) chips.push({ keys: ['excludeExpired'], label: 'Not expired' })
  if (drillDown.branchId) chips.push({ keys: ['branchId'], label: `Branch: ${branchName ?? 'Selected branch'}` })
  return chips
}
