import { useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useInvitationsBoard } from '../../../hooks/use-invitations-board'

export function useStaffDashboard() {
  const navigate = useNavigate()
  const board = useInvitationsBoard('/staff/login')

  const signOut = useCallback(() => {
    sessionStorage.removeItem('token')
    navigate('/staff/login')
  }, [navigate])

  return {
    ...board,
    signOut,
  }
}
