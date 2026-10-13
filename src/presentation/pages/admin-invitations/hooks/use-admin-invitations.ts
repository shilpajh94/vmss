import { useInvitationsBoard } from '../../../hooks/use-invitations-board'
import { usePageRefresh } from '../../../context/refresh-context'

export function useAdminInvitations() {
  const board = useInvitationsBoard('/admin/login', 'all')
  usePageRefresh({ refresh: board.refresh, isRefreshing: board.isLoading || board.isRefreshing, lastUpdatedAt: board.lastUpdatedAt })
  return board
}
