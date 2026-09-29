import { useInvitationsBoard } from '../../../hooks/use-invitations-board'
import { usePageRefresh } from '../../../context/refresh-context'

export function useAdminInvitations() {
  const board = useInvitationsBoard('/admin/login', 'all', { serverFilters: true })
  usePageRefresh({ refresh: board.refresh, isRefreshing: board.isLoading, lastUpdatedAt: board.lastUpdatedAt })
  return board
}
