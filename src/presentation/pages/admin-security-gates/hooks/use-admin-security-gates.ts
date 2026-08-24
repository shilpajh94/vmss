import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { SecurityGate } from '../../../../domain/entities/security-gate-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export function useAdminSecurityGates() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listSecurityGatesUseCase, deleteSecurityGateUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [securityGates, setSecurityGates] = useState<SecurityGate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<SecurityGate | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const loadSecurityGates = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, list] = await Promise.all([getCurrentStaffUserUseCase.execute(), listSecurityGatesUseCase.execute()])
      setCurrentUser(user)
      setSecurityGates(list)
    } catch {
      setErrorMessage('Something went wrong loading the security gates. Please try again.')
      toast.error('Something went wrong loading the security gates. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listSecurityGatesUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadSecurityGates()
  }, [navigate, loadSecurityGates])

  const retry = useCallback(() => {
    void loadSecurityGates()
  }, [loadSecurityGates])

  const requestDelete = useCallback((securityGate: SecurityGate) => {
    setPendingDelete(securityGate)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteSecurityGateUseCase.execute(pendingDelete.id)
      setSecurityGates((current) => current.filter((securityGate) => securityGate.id !== pendingDelete.id))
      toast.success('Security gate deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the security gate. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteSecurityGateUseCase, toast])

  return {
    currentUser,
    securityGates,
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
