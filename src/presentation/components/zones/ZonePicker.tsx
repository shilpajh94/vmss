import type { Zone } from '../../../domain/entities/zone-schema'
import { Checkbox } from '../ui/Checkbox'

interface ZonePickerProps {
  zones: Zone[]
  selectedIds: string[]
  onToggle: (zoneId: string, checked: boolean) => void
  /** `readonly` lists only the selected zones, with no controls. */
  mode: 'edit' | 'readonly'
  /** Shown beside a zone when zones from several branches are listed. */
  branchNames?: Map<string, string>
  /** The branch default zone: shown as a locked chip, never selectable or part of the selection. */
  alwaysAllowed?: Zone
}

function zoneLabel(zone: Zone, branchNames?: Map<string, string>): string {
  const branch = branchNames?.get(zone.branchId)
  return `${zone.name} (${zone.code})${branch ? ` · ${branch}` : ''}${zone.isActive ? '' : ' — inactive'}`
}

// A checkbox list of zones. An inactive zone can't be newly picked (the
// backend denies it anyway) but stays visible and unticking-able when
// already selected, so a stale choice can be removed.
export function ZonePicker({ zones, selectedIds, onToggle, mode, branchNames, alwaysAllowed }: ZonePickerProps) {
  const selected = new Set(selectedIds)
  const chip = alwaysAllowed ? (
    <span className="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-border-subtle px-3 py-1 font-body text-[13px] font-semibold text-text">
      {zoneLabel(alwaysAllowed)}
      <span className="rounded-full bg-admin-accent/15 px-2 py-0.5 text-[11px] font-bold text-admin-accent">Always allowed</span>
    </span>
  ) : null
  const selectable = alwaysAllowed ? zones.filter((zone) => zone.id !== alwaysAllowed.id) : zones

  if (mode === 'readonly') {
    const chosen = selectable.filter((zone) => selected.has(zone.id))
    if (chosen.length === 0) return chip ?? <p className="font-body text-sm text-text-faint">No zones.</p>
    return (
      <ul className="flex flex-wrap gap-2">
        {chip && <li>{chip}</li>}
        {chosen.map((zone) => (
          <li key={zone.id} className="rounded-full bg-border-subtle px-3 py-1 font-body text-[13px] font-semibold text-text">
            {zoneLabel(zone, branchNames)}
          </li>
        ))}
      </ul>
    )
  }

  if (selectable.length === 0) return chip ?? <p className="font-body text-sm text-text-faint">No zones are defined for this selection yet.</p>

  // Active zones first, each group by name.
  const ordered = [...selectable].sort((a, b) => Number(b.isActive) - Number(a.isActive) || a.name.localeCompare(b.name))
  return (
    <div className="flex flex-col gap-3">
      {chip}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {ordered.map((zone) => {
        const isSelected = selected.has(zone.id)
        const isLocked = !zone.isActive && !isSelected
        return (
          <div key={zone.id} className={isLocked ? 'opacity-50' : undefined}>
            <Checkbox checked={isSelected} onChange={(checked) => !isLocked && onToggle(zone.id, checked)}>
              {zoneLabel(zone, branchNames)}
            </Checkbox>
          </div>
        )
      })}
      </div>
    </div>
  )
}
