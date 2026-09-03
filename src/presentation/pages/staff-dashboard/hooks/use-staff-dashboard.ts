import { useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useInvitationsBoard } from '../../../hooks/use-invitations-board'
import { usePushNotifications } from '../../../hooks/use-push-notifications'

export function useStaffDashboard() {
  const navigate = useNavigate()
  const board = useInvitationsBoard('/staff/login', 'mine')
  const { unregisterCurrentDevice } = usePushNotifications()

  const signOut = useCallback(() => {
    void unregisterCurrentDevice().finally(() => {
      sessionStorage.removeItem('token')
      navigate('/staff/login')
    })
  }, [navigate, unregisterCurrentDevice])

  return {
    ...board,
    signOut,
  }
}
