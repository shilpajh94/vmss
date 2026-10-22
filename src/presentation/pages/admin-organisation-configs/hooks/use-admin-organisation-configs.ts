import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDependencies } from '../../../context/app-dependencies-context'
import { useToast } from '../../../components/toast/toast-context'
import { usePageRefresh } from '../../../context/refresh-context'
import { useLoadTracker, type LoadMode } from '../../../hooks/use-load-tracker'
import { useUnsavedChanges } from '../../../hooks/use-unsaved-changes'
import { useUnsavedChangesGuard } from '../../../hooks/use-unsaved-changes-guard'
import type { OrganisationConfig } from '../../../../domain/entities/organisation-config-schema'
import type { StaffUser } from '../../../../domain/entities/staff-user-schema'
import { toIanaTimezone } from '../../../utils/timezones'
import { toUserMessage } from '../../../utils/to-user-message'

// A legacy `GMT±HH:MM` value is shown, and saved next time, as its IANA zone
// (design D-W8). Applied to the saved copy too, so the upgrade alone doesn't
// count as an unsaved change.
function withIanaTimezone(config: OrganisationConfig): OrganisationConfig {
  return { ...config, defaultTimezone: toIanaTimezone(config.defaultTimezone) }
}

export function useAdminOrganisationConfigs() {
  const navigate = useNavigate()
  const { getCurrentStaffUserUseCase, getOrganisationConfigUseCase, updateOrganisationConfigUseCase } = useAppDependencies()
  const toast = useToast()

  const [currentUser, setCurrentUser] = useState<StaffUser | undefined>(undefined)
  const [savedConfig, setSavedConfig] = useState<OrganisationConfig | undefined>(undefined)
  const [form, setForm] = useState<OrganisationConfig | undefined>(undefined)
  const { phase, isRefreshing, begin } = useLoadTracker()
  const [isSaving, setIsSaving] = useState(false)
  const [nameError, setNameError] = useState<string | undefined>(undefined)

  const loadConfig = useCallback(
    async (mode: LoadMode = 'user') => {
      const request = begin(mode)

      try {
        const [user, config] = await Promise.all([getCurrentStaffUserUseCase.execute(), getOrganisationConfigUseCase.execute()])
        if (!request.succeed()) return
        setCurrentUser(user)
        setSavedConfig(withIanaTimezone(config))
        setForm(withIanaTimezone(config))
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

  const updateField = useCallback(<K extends keyof OrganisationConfig>(key: K, value: OrganisationConfig[K]) => {
    if (key === 'organisationName') setNameError(undefined)
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }, [])

  // A form page: never polled. The top-bar refresh reloads the saved config
  // (dropping any unsaved edits), and asks first when there are any.
  const hasUnsavedChanges = useUnsavedChanges(savedConfig, form)
  const reload = useCallback(() => {
    void loadConfig()
  }, [loadConfig])

  usePageRefresh({ refresh: reload, isRefreshing: phase === 'initial' || isRefreshing, hasUnsavedChanges })
  useUnsavedChangesGuard(hasUnsavedChanges)

  const cancel = useCallback(() => {
    setForm(savedConfig)
    setNameError(undefined)
  }, [savedConfig])

  const save = useCallback(async () => {
    if (!form) return
    const organisationName = form.organisationName.trim()
    if (!organisationName) {
      setNameError('Organisation name is required.')
      return
    }

    setIsSaving(true)
    try {
      const updated = withIanaTimezone(await updateOrganisationConfigUseCase.execute({ ...form, organisationName }))
      setSavedConfig(updated)
      setForm(updated)
      toast.success('Organisation configuration saved.')
    } catch (error) {
      toast.error(toUserMessage(error, 'Something went wrong saving the organisation configuration. Please try again.'))
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
    nameError,
    retry,
    updateField,
    cancel,
    save,
  }
}
