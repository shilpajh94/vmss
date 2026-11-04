import type { InsideVisitor } from '../../../domain/entities/emergency-inside-schema'
import { AsyncRegion } from '../../components/AsyncRegion'
import { PageContentLayout } from '../../components/PageContentLayout'
import { EmptyState } from '../../components/ui/EmptyState'
import { ListSkeleton } from '../../components/ui/Skeleton'
import { SelectField } from '../../components/ui/SelectField'
import { usePageHeader } from '../../context/page-header-context'
import { formatTime } from '../../utils/format-time'
import { useEmergencyInside } from './hooks/use-emergency-inside'

function VisitorTable({ visitors }: { visitors: InsideVisitor[] }) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="bg-border-subtle">
            {['VISITOR', 'HOST', 'BADGE', 'ENTERED'].map((header) => (
              <th key={header} className="px-4 py-2.5 font-body text-xs font-bold text-text-muted whitespace-nowrap">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visitors.map((visitor) => (
            <tr key={`${visitor.invitationId}-${visitor.visitorName}`} className="border-b border-border-subtle last:border-b-0">
              <td className="px-4 py-3 font-body text-sm font-semibold text-text">{visitor.visitorName}</td>
              <td className="px-4 py-3 font-body text-sm text-text-muted">{visitor.hostName || '—'}</td>
              <td className="px-4 py-3 font-body text-sm text-text-faint whitespace-nowrap">{visitor.badgeNumber || '—'}</td>
              <td className="px-4 py-3 font-body text-sm text-text-faint whitespace-nowrap">{visitor.enteredAt ? formatTime(visitor.enteredAt) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ZoneGroup({ title, visitors }: { title: string; visitors: InsideVisitor[] }) {
  return (
    <section aria-label={title} className="overflow-hidden rounded-2xl border border-border bg-surface">
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <h2 className="font-display text-base font-bold text-text">{title}</h2>
        <span className="rounded-full bg-border-subtle px-2.5 py-1 font-body text-xs font-semibold text-text-secondary">{visitors.length} inside</span>
      </header>
      {visitors.length === 0 ? <p className="px-4 py-3 font-body text-sm text-text-faint">Nobody inside.</p> : <VisitorTable visitors={visitors} />}
    </section>
  )
}

export function EmergencyInsidePage() {
  const inside = useEmergencyInside()
  const { report, phase } = inside

  usePageHeader({ description: 'Everyone currently inside the premises, grouped by zone' })

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-end justify-between gap-3">
            <div className="flex flex-col gap-1">
              <h1 className="font-display text-xl font-bold md:text-2xl text-text">Inside by zone</h1>
              <p className="font-body text-sm text-text-muted" aria-live="polite">
                {report ? `${report.totalInside} inside` : ' '}
                {inside.lastLoadedAt ? ` · updated ${formatTime(inside.lastLoadedAt.toISOString())}` : ''}
              </p>
            </div>
            <div className="w-full sm:w-56">
              <SelectField label="Branch" value={inside.branchFilter} onChange={inside.setBranchFilter} placeholder="All branches" placeholderSelectable options={inside.branchOptions} />
            </div>
          </div>
        </>
      }
    >
      <AsyncRegion
        phase={phase}
        isRefreshing={inside.isRefreshing}
        skeleton={<ListSkeleton rows={4} label="Loading who is inside…" />}
        errorMessage={inside.isFeatureOff ? 'Zone access control is not enabled for this environment.' : 'Something went wrong loading who is inside. Please try again.'}
        onRetry={inside.isFeatureOff ? undefined : inside.retry}
        isEmpty={report?.totalInside === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            <EmptyState message="Nobody is inside right now." />
          </div>
        }
      >
        <div className="flex flex-col gap-4">
          {report?.zones.map((zone) => <ZoneGroup key={zone.zoneId} title={zone.zoneName} visitors={zone.visitors} />)}
          {report && report.unzoned.length > 0 && <ZoneGroup title="Not in a zone" visitors={report.unzoned} />}
        </div>
      </AsyncRegion>
    </PageContentLayout>
  )
}
