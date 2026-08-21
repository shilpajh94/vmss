import { ClockIcon, PlusIcon } from '../../../components/icons'
import { EmptyState } from '../../../components/ui/EmptyState'
import type { DashboardUpcomingVisitor } from '../../../../domain/entities/dashboard-overview-schema'

interface UpcomingVisitorsCardProps {
  visitors: DashboardUpcomingVisitor[]
  checkingInIds: string[]
  onCheckIn: (id: string) => void
  onPreRegister: () => void
}

export function UpcomingVisitorsCard({ visitors, checkingInIds, onCheckIn, onPreRegister }: UpcomingVisitorsCardProps) {
  return (
    <div className="flex w-full flex-col gap-5 rounded-2xl border border-border bg-surface p-6">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-0.5">
          <h2 className="font-display text-lg font-bold text-text">Upcoming Pre-Registered Visitors</h2>
          <p className="font-body text-sm text-text-faint">Scheduled visitors for the remainder of today</p>
        </div>
        <button
          type="button"
          onClick={onPreRegister}
          className="flex items-center gap-2 rounded-full bg-admin-accent px-[18px] py-2.5 font-body text-[13px] font-semibold text-white"
        >
          <PlusIcon className="size-3.5" />
          Pre-Register Visitor
        </button>
      </div>

      {visitors.length === 0 ? (
        <EmptyState message="No upcoming visitors scheduled." className="py-12" />
      ) : (
        <div className="flex flex-col">
          {visitors.map((visitor) => {
            const isCheckingIn = checkingInIds.includes(visitor.id)

            return (
              <div key={visitor.id} className="flex flex-wrap items-center gap-4 border-t border-border-subtle py-4 first:border-t-0">
                <div className="flex w-32 shrink-0 items-center gap-2 font-body text-sm font-semibold text-text">
                  <ClockIcon className="size-4 text-text-faint" />
                  {visitor.time}
                </div>

                <div className="flex flex-1 items-center gap-3 basis-56">
                  <span className="size-7 shrink-0 rounded-full bg-neutral-subtle" />
                  <div className="flex flex-col">
                    <span className="font-body text-sm font-semibold text-text">{visitor.visitorName}</span>
                    <span className="font-body text-xs text-text-faint">{visitor.company}</span>
                  </div>
                </div>

                <div className="flex basis-44 items-center gap-1 font-body text-sm text-text-muted">
                  <span>Host:</span>
                  <span className="font-semibold text-text">{visitor.hostName}</span>
                </div>

                <div className="flex basis-52 items-center gap-2 font-body text-sm text-text-muted">
                  <span className="size-1.5 rounded-full bg-admin-accent" />
                  {visitor.purpose}
                </div>

                <div className="ml-auto flex items-center gap-2">
                  <button type="button" className="rounded-lg border border-border bg-surface px-3.5 py-2 font-body text-[13px] font-semibold text-text">
                    Print Pass
                  </button>
                  <button
                    type="button"
                    disabled={isCheckingIn}
                    onClick={() => onCheckIn(visitor.id)}
                    className="rounded-lg bg-admin-accent px-3.5 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-60"
                  >
                    {isCheckingIn ? 'Checking in…' : 'Check In'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
