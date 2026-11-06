import type { Zone } from '../../../domain/entities/zone-schema'
import { ErrorState } from '../ui/ErrorState'
import { Skeleton } from '../ui/Skeleton'
import { ZonePicker } from './ZonePicker'

interface ZoneDraftSectionProps {
  zones: Zone[]
  selectedIds: string[]
  onToggle: (zoneId: string, checked: boolean) => void
  phase: 'loading' | 'ready' | 'error'
  onRetry: () => void
  branchNames?: Map<string, string>
  title?: string
}

// The zone checklist for a category that does not exist yet: a plain draft
// the form saves after the category is created (no load or save of its own).
export function ZoneDraftSection({ zones, selectedIds, onToggle, phase, onRetry, branchNames, title = 'Default zones' }: ZoneDraftSectionProps) {
  return (
    <section aria-label={title} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h3 className="font-body text-sm font-semibold text-text-muted">{title}</h3>
        <p className="font-body text-xs text-text-faint">
          Zones every visit in this category may enter unless the visit sets its own. The branch default zone is pre-selected; untick it if this category should not list it.
        </p>
      </div>
      {phase === 'loading' ? (
        <Skeleton className="h-16 w-full rounded-xl" />
      ) : phase === 'error' ? (
        <ErrorState message="Something went wrong loading the zones. Please try again." onRetry={onRetry} />
      ) : (
        <ZonePicker zones={zones} selectedIds={selectedIds} onToggle={onToggle} mode="edit" branchNames={branchNames} />
      )}
    </section>
  )
}
