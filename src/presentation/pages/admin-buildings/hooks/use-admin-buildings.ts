import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { Building } from '../../../../domain/entities/building-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export function useAdminBuildings() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, listBuildingsUseCase, deleteBuildingUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [buildings, setBuildings] = useState<Building[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const [pendingDelete, setPendingDelete] = useState<Building | undefined>(undefined)
  const [isDeleting, setIsDeleting] = useState(false)

  const loadBuildings = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, list] = await Promise.all([getCurrentStaffUserUseCase.execute(), listBuildingsUseCase.execute()])
      setCurrentUser(user)
      setBuildings(list)
    } catch {
      setErrorMessage('Something went wrong loading the buildings. Please try again.')
      toast.error('Something went wrong loading the buildings. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, listBuildingsUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    void loadBuildings()
  }, [navigate, loadBuildings])

  const retry = useCallback(() => {
    void loadBuildings()
  }, [loadBuildings])

  const requestDelete = useCallback((building: Building) => {
    setPendingDelete(building)
  }, [])

  const cancelDelete = useCallback(() => {
    setPendingDelete(undefined)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return

    setIsDeleting(true)
    try {
      await deleteBuildingUseCase.execute(pendingDelete.id)
      setBuildings((current) => current.filter((building) => building.id !== pendingDelete.id))
      toast.success('Building deleted.')
      setPendingDelete(undefined)
    } catch {
      toast.error('Something went wrong deleting the building. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }, [pendingDelete, deleteBuildingUseCase, toast])

  return {
    currentUser,
    buildings,
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
