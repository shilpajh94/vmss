import type { ReactNode } from 'react'
import { LoadingState } from '../ui/LoadingState'
import { DashboardLoadError } from '../dashboard/DashboardStates'
import type { StaffSession } from './use-staff-session'

// What a layout shows inside its shell before its pages may render: a
// loading state while `/auth/me` resolves, or its failure with a retry.
// Pages never render without a user (design D-W3, QA F7).
export function SessionGateContent({ session, onRetry, children }: { session: StaffSession; onRetry: () => void; children: ReactNode }) {
  if (session.status === 'ready') return <>{children}</>
  if (session.status === 'error') {
    return <DashboardLoadError message="We couldn't load your account. Check your connection and try again." onRetry={onRetry} />
  }
  return <LoadingState label="Loading your workspace…" className="flex-1" />
}
