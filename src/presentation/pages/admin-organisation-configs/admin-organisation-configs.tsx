import { SlidersIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { usePageHeader } from '../../context/page-header-context'
import { GeneralInformationCard } from './Components/GeneralInformationCard'
import { VisitorPolicyCard } from './Components/VisitorPolicyCard'
import { useAdminOrganisationConfigs } from './hooks/use-admin-organisation-configs'

export function AdminOrganisationConfigsPage() {
  const { form, isLoading, isSaving, errorMessage, logoPreview, retry, updateField, previewLogo, setLogoPreview, cancel, save } =
    useAdminOrganisationConfigs()

  usePageHeader({ description: 'Update global configuration, visitor policy, and notification preferences' })

  return (
    <>
      <div className="flex w-full items-center justify-between">
        <h1 className="font-display text-2xl font-bold text-text">Organisation Configurations</h1>
        <button
          type="button"
          className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
        >
          <SlidersIcon className="size-3.5" />
          Filters
        </button>
      </div>

      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading || !form ? (
        <LoadingState label="Loading organisation configuration…" className="flex-1" />
      ) : (
        <>
          <div className="flex w-full items-start gap-6">
            <GeneralInformationCard
              form={form}
              logoPreview={logoPreview}
              onNameChange={(organisationName) => updateField('organisationName', organisationName)}
              onTimezoneChange={(defaultTimezone) => updateField('defaultTimezone', defaultTimezone)}
              onPreviewLogo={previewLogo}
              onLogoPreviewChange={setLogoPreview}
            />
            <VisitorPolicyCard
              form={form}
              onAutoApproveChange={(autoApprovePreRegistered) => updateField('autoApprovePreRegistered', autoApprovePreRegistered)}
            />
          </div>

          <div className="flex w-full max-w-[536px] items-start justify-end gap-3 pt-5">
            <button
              type="button"
              onClick={cancel}
              disabled={isSaving}
              className="rounded-full border border-border bg-surface px-[18px] py-2.5 font-body text-[13px] font-semibold text-text disabled:opacity-50"
            >
              Cancel Changes
            </button>
            <button
              type="button"
              onClick={() => void save()}
              disabled={isSaving}
              className="rounded-full bg-admin-accent px-[18px] py-2.5 font-body text-[13px] font-semibold text-white disabled:opacity-50"
            >
              {isSaving ? 'Saving…' : 'Save Configs'}
            </button>
          </div>
        </>
      )}
    </>
  )
}
