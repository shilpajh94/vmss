import { SlidersIcon } from '../../components/icons'
import { AsyncRegion } from '../../components/AsyncRegion'
import { FormSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { PRESS_FEEDBACK_CLASS } from '../../components/ui/interactive'
import { usePageHeader } from '../../context/page-header-context'
import { GeneralInformationCard } from './Components/GeneralInformationCard'
import { KioskLocationValidationCard } from './Components/KioskLocationValidationCard'
import { VisitorPolicyCard } from './Components/VisitorPolicyCard'
import { useAdminOrganisationConfigs } from './hooks/use-admin-organisation-configs'

export function AdminOrganisationConfigsPage() {
  const { form, phase, isRefreshing, isSaving, retry, updateField, cancel, save } =
    useAdminOrganisationConfigs()

  usePageHeader({ description: 'Update global configuration, visitor policy, and notification preferences' })

  return (
    <>
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-xl font-bold md:text-2xl text-text">Organisation Configurations</h1>
        <button
          type="button"
          className={`flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`}
        >
          <SlidersIcon className="size-3.5" />
          Filters
        </button>
      </div>

      <AsyncRegion
        phase={phase}
        isRefreshing={isRefreshing}
        skeleton={
          // Same two side-by-side cards as the loaded form.
          <div className="flex w-full flex-col gap-6 lg:flex-row lg:items-start">
            <FormSkeleton rows={3} columns={1} className="flex-1" label="Loading organisation configuration…" />
            <FormSkeleton rows={1} columns={1} className="flex-1" label="Loading visitor policy…" />
          </div>
        }
        errorMessage="Something went wrong loading the organisation configuration. Please try again."
        onRetry={retry}
      >
        {form && (
          <>
            {/* Side by side from lg; stacked below, so neither card is pushed
                past a phone's edge (app-shell "Staff and admin pages fit every
                supported device width"). */}
            <div className="flex w-full flex-col gap-6 lg:flex-row lg:items-start">
              <GeneralInformationCard
                form={form}
                onNameChange={(organisationName) => updateField('organisationName', organisationName)}
                onTimezoneChange={(defaultTimezone) => updateField('defaultTimezone', defaultTimezone)}
                onLogoUrlChange={(logoUrl) => updateField('logoUrl', logoUrl)}
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
              <PendingButton
                onClick={() => void save()}
                pending={isSaving}
                pendingLabel="Saving…"
                className="rounded-full bg-admin-accent px-[18px] py-2.5 font-body text-[13px] font-semibold text-on-accent disabled:opacity-50"
              >
                Save Configs
              </PendingButton>
            </div>
          </>
        )}
      </AsyncRegion>

      <KioskLocationValidationCard />
    </>
  )
}
