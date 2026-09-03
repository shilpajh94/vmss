import { useCallback, useEffect, useMemo, useState } from 'react'
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

  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)
  const [buildingFilter, setBuildingFilter] = useState('')
  const [gateTypeFilter, setGateTypeFilter] = useState('')
  const [securityLevelFilter, setSecurityLevelFilter] = useState('')

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

  const buildingOptions = useMemo(() => {
    const seen = new Map<string, string>()
    for (const gate of securityGates) {
      if (!seen.has(gate.buildingId)) seen.set(gate.buildingId, gate.buildingName)
    }
    return [...seen.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label))
  }, [securityGates])

  const filteredSecurityGates = useMemo(() => {
    return securityGates.filter((gate) => {
      if (buildingFilter && gate.buildingId !== buildingFilter) return false
      if (gateTypeFilter && gate.gateType !== gateTypeFilter) return false
      if (securityLevelFilter && (securityLevelFilter === 'high') !== gate.highSecurity) return false
      return true
    })
  }, [securityGates, buildingFilter, gateTypeFilter, securityLevelFilter])

  const isFiltering = buildingFilter !== '' || gateTypeFilter !== '' || securityLevelFilter !== ''
  const toggleFilterPanel = useCallback(() => setIsFilterPanelOpen((current) => !current), [])
  const clearFilters = useCallback(() => {
    setBuildingFilter('')
    setGateTypeFilter('')
    setSecurityLevelFilter('')
  }, [])

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
    securityGates: filteredSecurityGates,
    hasAnySecurityGates: securityGates.length > 0,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    buildingOptions,
    buildingFilter,
    setBuildingFilter,
    gateTypeFilter,
    setGateTypeFilter,
    securityLevelFilter,
    setSecurityLevelFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
