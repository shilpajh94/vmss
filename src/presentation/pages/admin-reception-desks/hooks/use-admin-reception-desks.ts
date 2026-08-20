import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { ReceptionDesk } from '../../../../domain/entities/reception-desk-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export function useAdminReceptionDesks() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listReceptionDesksUseCase, deleteReceptionDeskUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [receptionDesks, setReceptionDesks] = useState<ReceptionDesk[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<ReceptionDesk | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const loadReceptionDesks = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, list] = await Promise.all([getCurrentStaffUserUseCase.execute(), listReceptionDesksUseCase.execute()])
      setCurrentUser(user)
      setReceptionDesks(list)
    } catch {
      setErrorMessage('Something went wrong loading the reception desks. Please try again.')
      toast.error('Something went wrong loading the reception desks. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listReceptionDesksUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    void loadReceptionDesks()
  }, [navigate, loadReceptionDesks])

  const retry = useCallback(() => {
    void loadReceptionDesks()
  }, [loadReceptionDesks])

  const requestDelete = useCallback((receptionDesk: ReceptionDesk) => {
    setPendingDelete(receptionDesk)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteReceptionDeskUseCase.execute(pendingDelete.id)
      setReceptionDesks((current) => current.filter((receptionDesk) => receptionDesk.id !== pendingDelete.id))
      toast.success('Reception desk deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the reception desk. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteReceptionDeskUseCase, toast])

  return {
    currentUser,
    receptionDesks,
    isLoading,
    errorMessage,
    retry,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
