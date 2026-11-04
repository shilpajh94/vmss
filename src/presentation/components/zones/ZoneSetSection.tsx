import { useZoneFeature } from '../../context/zone-feature-context'
import { useZoneSet, type ZoneSetScope } from '../../hooks/use-zone-set'
import { AlertTriangleIcon } from '../icons'
import { ErrorState } from '../ui/ErrorState'
import { PendingButton } from '../ui/PendingButton'
import { Skeleton } from '../ui/Skeleton'
import { ZonePicker } from './ZonePicker'

interface ZoneSetSectionProps {
  scope: ZoneSetScope
  title?: string
  /** Whether the user may save (`zones:manage` for a category, `invitations:edit` for a visit). */
  canEdit: boolean
  /** Rendered tighter inside a modal or a success panel. */
  compact?: boolean
}

function Notice({ tone, children }: { tone: 'warning' | 'info'; children: React.ReactNode }) {
  return (
    <p
      role={tone === 'warning' ? 'alert' : 'status'}
      className={`flex items-start gap-2 rounded-xl border px-3.5 py-2.5 font-body text-[13px] text-text ${
        tone === 'warning' ? 'border-warning/40 bg-warning/10' : 'border-border bg-border-subtle'
      }`}
    >
      {tone === 'warning' && <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-warning" />}
      <span>{children}</span>
    </p>
  )
}

// The zone picker for one category or visit, with its own load and save. It
// renders nothing unless the zone feature is on and the user holds
// `zones:view` (both folded into `useZoneFeature().enabled`).
export function ZoneSetSection({ scope, title = 'Zone access', canEdit, compact = false }: ZoneSetSectionProps) {
  const { enabled } = useZoneFeature()
  const zoneSet = useZoneSet(scope, enabled)
  if (!enabled) return null

  const isCategory = scope.kind === 'category'

  return (
    <section aria-label={title} className={`flex flex-col ${compact ? 'gap-3' : 'gap-4'}`}>
      <div className="flex flex-col gap-1">
        <h3 className="font-body text-sm font-semibold text-text-muted">{title}</h3>
        <p className="font-body text-xs text-text-faint">
          {isCategory
            ? 'Zones every visit in this category may enter unless the visit sets its own.'
            : 'Saving replaces the zones this visit may enter. Leave it empty to use the category defaults.'}
        </p>
      </div>

      {zoneSet.phase === 'loading' ? (
        <Skeleton className="h-16 w-full rounded-xl" />
      ) : zoneSet.phase === 'error' ? (
        <ErrorState message="Something went wrong loading the zones. Please try again." onRetry={() => void zoneSet.retry()} />
      ) : (
        <>
          {zoneSet.deniesEverything && (
            <Notice tone="warning">
              {isCategory
                ? 'No default zones are set. Visits in this category without their own zones will be denied every zone.'
                : 'No zones are mapped to this visit or its category. Every zone will be denied for this visit.'}
            </Notice>
          )}
          {zoneSet.usingCategoryDefaults && <Notice tone="info">This visit has no zones of its own, so its category defaults apply.</Notice>}

          {canEdit ? (
            <ZonePicker zones={zoneSet.zones} selectedIds={zoneSet.draft} onToggle={zoneSet.toggle} mode="edit" branchNames={isCategory ? zoneSet.branchNames : undefined} />
          ) : (
            <ZonePicker zones={zoneSet.zones} selectedIds={zoneSet.effectiveIds} onToggle={() => {}} mode="readonly" branchNames={isCategory ? zoneSet.branchNames : undefined} />
          )}

          {zoneSet.saveError && (
            <p role="alert" className="font-body text-[13px] text-danger">
              {zoneSet.saveError}
            </p>
          )}

          {canEdit && (
            <div className="flex flex-wrap items-center gap-3">
              <PendingButton
                onClick={() => void zoneSet.save()}
                pending={zoneSet.isSaving}
                pendingLabel="Saving…"
                disabled={!zoneSet.isDirty}
                className="rounded-full bg-admin-accent px-5 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
              >
                Save zones
              </PendingButton>
              {!isCategory && zoneSet.draft.length > 0 && (
                <button type="button" onClick={zoneSet.clear} className="font-body text-[13px] font-semibold text-admin-accent">
                  Clear (use category defaults)
                </button>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}
