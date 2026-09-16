import { PlusIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { usePageHeader } from '../../context/page-header-context'
import { CreateStepModal } from './Components/CreateStepModal'
import { StepCard } from './Components/StepCard'
import { DEFAULT_WORKSPACE_VALUE, useAdminFormBuilder } from './hooks/use-admin-form-builder'

export function AdminFormBuilderPage() {
  const {
    branches,
    selectedBranchId,
    selectWorkspace,
    steps,
    isLoading,
    errorMessage,
    retry,
    toggleStepActive,
    pendingDelete,
    requestDeleteStep,
    cancelDeleteStep,
    confirmDeleteStep,
    isCreateOpen,
    openCreateStep,
    closeCreateStep,
    createStep,
    goToEditFields,
    isPublishing,
    publish,
  } = useAdminFormBuilder()

  usePageHeader({ description: 'Customize your visitor registration workflows' })

  return (
    <>
      <div className="flex w-full flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-text">Form Builder</h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-64">
            <SelectField
              label=""
              value={selectedBranchId ?? DEFAULT_WORKSPACE_VALUE}
              onChange={selectWorkspace}
              placeholderSelectable
              placeholder="Tenant Default"
              options={[
                { value: DEFAULT_WORKSPACE_VALUE, label: 'Tenant Default' },
                ...branches.map((branch) => ({ value: branch.id, label: branch.name })),
              ]}
            />
          </div>
          <button
            type="button"
            disabled
            title="Coming soon"
            className="cursor-not-allowed rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text-faint opacity-60"
          >
            Form Preview
          </button>
          <button
            type="button"
            onClick={() => void publish()}
            disabled={isPublishing}
            className="rounded-full bg-admin-accent px-[18px] py-2.5 font-body text-[13px] font-semibold text-white disabled:opacity-60"
          >
            {isPublishing ? 'Publishing…' : 'Publish Changes'}
          </button>
        </div>
      </div>

      <h2 className="font-display text-lg font-bold text-text">Registration Steps</h2>

      <button
        type="button"
        onClick={openCreateStep}
        className="flex w-full items-center justify-center gap-2 rounded-2xl border border-dashed border-border bg-surface py-4 font-body text-sm font-semibold text-admin-accent"
      >
        <PlusIcon className="size-4" />
        Create Registration Step
      </button>

      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading registration steps…" className="flex-1" />
      ) : steps.length === 0 ? (
        <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
          <EmptyState message="No registration steps yet." />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {steps.map((step, index) => (
            <StepCard
              key={step.id}
              step={step}
              order={index + 1}
              onToggleActive={() => void toggleStepActive(step)}
              onEditFields={() => goToEditFields(step)}
              onDelete={() => requestDeleteStep(step)}
            />
          ))}
        </div>
      )}

      <CreateStepModal isOpen={isCreateOpen} onClose={closeCreateStep} onCreate={(name) => void createStep(name)} />

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Remove Registration Step"
        message={`Are you sure you want to remove "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel="Remove"
        onConfirm={() => void confirmDeleteStep()}
        onCancel={cancelDeleteStep}
      />
    </>
  )
}
