import { useInvitationsBoard } from '../../../hooks/use-invitations-board'
import { usePageHeader } from '../../../context/page-header-context'
import { usePageRefresh } from '../../../context/refresh-context'

export function useStaffInvitations() {
  const board = useInvitationsBoard('/staff/login', 'mine')
  usePageHeader({ description: 'Track visitor invitations, approval status, and check-in progress' })
  usePageRefresh({ refresh: board.refresh, isRefreshing: board.isLoading || board.isRefreshing, lastUpdatedAt: board.lastUpdatedAt })
  return board
}
