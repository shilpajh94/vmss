import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import type { OrganisationConfig } from '../../../../domain/entities/organisation-config-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'

export function useAdminOrganisationConfigs() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, getOrganisationConfigUseCase, updateOrganisationConfigUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [savedConfig, setSavedConfig] = useState<OrganisationConfig | undefined>(undefined)
  const [form, setForm] = useState<OrganisationConfig | undefined>(undefined)
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [isSaving, setIsSaving] = useState(false)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | undefined>(undefined)
  // The backend has no endpoint to store an uploaded logo file (only a logoUrl
  // string on /company), so a picked file is a local, unsaved preview only.
  const [logoPreview, setLogoPreviewState] = useState<{ url: string; fileName: string } | undefined>(undefined)

  const loadConfig = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, config] = await Promise.all([getCurrentStaffUserUseCase.execute(), getOrganisationConfigUseCase.execute()])
        if (!request.succeed()) return
        setCurrentUser(user)
        setSavedConfig(config)
        setForm(config)
        setLastUpdatedAt(new Date())
      } catch {
        if (!request.fail()) return
        toast.error('Something went wrong loading the organisation configuration. Please try again.')
      }
    },
    [begin, getCurrentStaffUserUseCase, getOrganisationConfigUseCase, toast],
  )

  useEffect(() => {
    if (!sessionStorage.getItem('token')) {
      navigate('/admin/login', { replace: true })
      return
    }

    void loadConfig()
  }, [navigate, loadConfig])

  const retry = useCallback(() => {
    void loadConfig()
  }, [loadConfig])

  usePageRefresh({ refresh: retry, isRefreshing: phase === 'initial' || isRefreshing, lastUpdatedAt })

  const updateField = useCallback(<K extends keyof OrganisationConfig>(key: K, value: OrganisationConfig[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }, [])

  const previewLogo = useCallback(async (file: File) => URL.createObjectURL(file), [])

  const setLogoPreview = useCallback((fileRef: string | undefined, fileName: string | undefined) => {
    setLogoPreviewState((current) => {
      if (current) URL.revokeObjectURL(current.url)
      return fileRef && fileName ? { url: fileRef, fileName } : undefined
    })
  }, [])

  const cancel = useCallback(() => {
    setForm(savedConfig)
    setLogoPreview(undefined, undefined)
  }, [savedConfig, setLogoPreview])

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
    phase,
    isRefreshing,
    isSaving,
    logoPreview,
    retry,
    updateField,
    previewLogo,
    setLogoPreview,
    cancel,
    save,
  }
}
