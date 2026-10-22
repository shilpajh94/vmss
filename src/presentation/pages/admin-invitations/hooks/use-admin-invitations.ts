import { useInvitationsBoard } from '../../../hooks/use-invitations-board'
import { usePageRefresh } from '../../../context/refresh-context'

export function useAdminInvitations() {
  const board = useInvitationsBoard('all')
  usePageRefresh({ refresh: board.refresh, isRefreshing: board.phase === 'initial' || board.isRefreshing })
  return board
}
