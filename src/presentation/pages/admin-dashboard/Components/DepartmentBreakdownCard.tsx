import { EmptyState } from '../../../components/ui/EmptyState'
import type { DashboardDepartmentBreakdown } from '../../../../domain/entities/dashboard-overview-schema'

interface DepartmentBreakdownCardProps {
  departments: DashboardDepartmentBreakdown[]
  activeDepartmentCount: number
}

const BAR_COLORS = ['bg-admin-accent', 'bg-secondary-accent', 'bg-info', 'bg-vip', 'bg-text-faint']

export function DepartmentBreakdownCard({ departments, activeDepartmentCount }: DepartmentBreakdownCardProps) {
  return (
    <div className="flex w-full max-w-md flex-col gap-5 rounded-2xl border border-border bg-surface p-6">
      <div className="flex flex-col gap-0.5">
        <h2 className="font-display text-lg font-bold text-text">Visitors by Department</h2>
        <p className="font-body text-sm text-text-faint">Distribution of today's visitors</p>
      </div>

      {departments.length === 0 ? (
        <EmptyState message="No department data yet." className="py-12" />
      ) : (
        <div className="flex flex-col gap-4">
          {departments.map((department, index) => (
            <div key={department.name} className="flex items-center gap-3">
              <span className="w-24 shrink-0 font-body text-sm text-text">{department.name}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-border-subtle">
                <div
                  className={`h-full rounded-full ${BAR_COLORS[index % BAR_COLORS.length]}`}
                  style={{ width: `${Math.min(department.percentage, 100)}%` }}
                />
              </div>
              <span className="w-16 shrink-0 text-right font-body text-sm">
                <span className="font-semibold text-text">{department.count}</span>{' '}
                <span className="text-text-faint">({department.percentage}%)</span>
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between border-t border-border-subtle pt-4">
        <span className="font-body text-sm text-text-faint">Total Registered departments</span>
        <span className="font-body text-sm font-semibold text-text">{activeDepartmentCount} Active</span>
      </div>
    </div>
  )
}
