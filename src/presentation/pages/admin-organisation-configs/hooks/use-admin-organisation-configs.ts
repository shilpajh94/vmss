import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import type { OrganisationConfig } from '../../../../domain/entities/organisation-config-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export function useAdminOrganisationConfigs() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, getOrganisationConfigUseCase, updateOrganisationConfigUseCase, uploadOrganisationLogoUseCase } =
    useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [savedConfig, setSavedConfig] = useState<OrganisationConfig | undefined>(undefined)
  const [form, setForm] = useState<OrganisationConfig | undefined>(undefined)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)

  const loadConfig = useCallback(async () => {
    setIsLoading(true)
    setErrorMessage(undefined)

    try {
      const [user, config] = await Promise.all([getCurrentStaffUserUseCase.execute(), getOrganisationConfigUseCase.execute()])
      setCurrentUser(user)
      setSavedConfig(config)
      setForm(config)
    } catch {
      setErrorMessage('Something went wrong loading the organisation configuration. Please try again.')
      toast.error('Something went wrong loading the organisation configuration. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [getCurrentStaffUserUseCase, getOrganisationConfigUseCase, toast])

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/staff/login', { replace: true })
      return
    }

    void loadConfig()
  }, [navigate, loadConfig])

  const retry = useCallback(() => {
    void loadConfig()
  }, [loadConfig])

  const updateField = useCallback(<K extends keyof OrganisationConfig>(key: K, value: OrganisationConfig[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }, [])

  const uploadLogo = useCallback(
    async (file: File) => {
      const { fileRef } = await uploadOrganisationLogoUseCase.execute(file)
      return fileRef
    },
    [uploadOrganisationLogoUseCase],
  )

  const setLogo = useCallback((logoUrl: string | undefined) => {
    setForm((current) => (current ? { ...current, logoUrl } : current))
  }, [])

  const cancel = useCallback(() => {
    setForm(savedConfig)
  }, [savedConfig])

  const save = useCallback(async () => {
    if (!form) return

    setIsSaving(true)
    try {
      const updated = await updateOrganisationConfigUseCase.execute(form)
      setSavedConfig(updated)
      setForm(updated)
      toast.success('Organisation configuration saved.')
    } catch {
      toast.error('Something went wrong saving the organisation configuration. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }, [form, updateOrganisationConfigUseCase, toast])

  return {
    currentUser,
    form,
    isLoading,
    isSaving,
    errorMessage,
    retry,
    updateField,
    uploadLogo,
    setLogo,
    cancel,
    save,
  }
}
