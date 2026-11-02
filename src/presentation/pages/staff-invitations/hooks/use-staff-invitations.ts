import { useInvitationsBoard } from '../../../hooks/use-invitations-board'
import { usePageHeader } from '../../../context/page-header-context'
import { usePageRefresh } from '../../../context/refresh-context'

export function useStaffInvitations() {
  const board = useInvitationsBoard('mine')
  usePageHeader({ description: 'Track visitor invitations, approval status, and check-in progress' })
  usePageRefresh({ refresh: board.refresh, isRefreshing: board.phase === 'initial' || board.isRefreshing, hasFailed: board.hasFailed })
  return board
}
