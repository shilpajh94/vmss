import { useInvitationsBoard } from '../../../hooks/use-invitations-board'

export function useAdminInvitations() {
  return useInvitationsBoard('/admin/login', 'all')
}
