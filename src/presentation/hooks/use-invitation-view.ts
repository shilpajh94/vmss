import { parseInvitationView, type InvitationView } from '../components/invitation-board/InvitationViewToggle'
import { useStoredState } from './use-stored-state'

// Board is the default; each portal remembers its own choice in this browser.
export function useInvitationView(portal: 'admin' | 'staff') {
  return useStoredState<InvitationView>(`invitations-view:${portal}`, 'board', parseInvitationView)
}
