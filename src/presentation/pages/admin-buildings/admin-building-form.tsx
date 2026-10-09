import { ChevronLeftIcon, PlusIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { usePageHeader } from '../../context/page-header-context'
import { FloorCard } from './Components/FloorCard'
import { FloorModal } from './Components/FloorModal'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { useAdminBuildingForm } from './hooks/use-admin-building-form'

export function AdminBuildingFormPage() {
  const {
    isEditMode,
    branches,
    departments,
    isLoading,
    errorMessage,
    retry,
    details,
    floors,
    expandedFloorIds,
    errors,
    isSaving,
    isSavingFloor,
    updateField,
    openAddFloorModal,
    openEditFloorModal,
    closeFloorModal,
    floorModal,
    saveFloor,
    requestDeleteFloor,
    cancelDeleteFloor,
    confirmDeleteFloor,
    pendingDeleteFloor,
    isDeletingFloor,
    toggleFloorExpanded,
    submit,
    cancel,
  } = useAdminBuildingForm()

  usePageHeader({ description: 'Administer branch premises, building access policies, and reception configurations' })

  const branchOptions = branches.map((branch) => ({ value: branch.id, label: branch.name }))
  const fieldLabelClassName = 'text-[13px] font-semibold text-[#475569]'

  return (
    <>
      <div className="mx-auto flex w-full max-w-[1160px] flex-col gap-6">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={cancel}
            aria-label="Back"
            className="flex size-9 items-center justify-center rounded-full border border-border bg-surface"
          >
            <ChevronLeftIcon className="size-4" />
          </button>
          <h1 className="font-display text-xl font-bold md:text-2xl text-text">{isEditMode ? 'Edit Building' : 'Add Building'}</h1>
        </div>

        {errorMessage ? (
          <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6 text-center md:p-12">
            <p className="font-body text-sm text-danger">{errorMessage}</p>
            <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
              Try again
            </button>
          </div>
        ) : isLoading ? (
          <LoadingState label="Loading…" className="py-12" />
        ) : (
          <div className="flex w-full flex-col gap-7 rounded-2xl border border-border bg-surface px-6 py-8">
            <div className="flex flex-col gap-4">
              <p className="font-body text-sm font-semibold text-text-muted">Building Details</p>
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <TextField
                    label="Building Name"
                    value={details.name}
                    onChange={(name) => updateField('name', name)}
                    error={errors.name}
                    labelClassName={fieldLabelClassName}
                  />
                </div>
                <div className="flex-1">
                  <SelectField
                    label="Branch"
                    value={details.branchId}
                    onChange={(branchId) => updateField('branchId', branchId)}
                    options={branchOptions}
                    placeholder="Select associated branch..."
                    error={errors.branchId}
                    labelClassName={fieldLabelClassName}
                  />
                </div>
              </div>
              <div className="flex flex-col gap-4 md:flex-row md:gap-6">
                <div className="flex-1">
                  <TextField
                    label="Building Code"
                    value={details.code}
                    onChange={(code) => updateField('code', code)}
                    error={errors.code}
                    labelClassName={fieldLabelClassName}
                  />
                </div>
                <div className="flex-1">
                  <TextField
                    label="Street Address"
                    value={details.address}
                    onChange={(address) => updateField('address', address)}
                    labelClassName={fieldLabelClassName}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between py-2">
                <div className="flex flex-col gap-1">
                  <p className="font-body text-sm font-semibold text-text-muted">Building Status</p>
                  <p className="font-body text-xs text-text-faint">Set active state to allow access allocation and visitor intake checks</p>
                </div>
                <ToggleSwitch
                  label={details.isActive ? 'Active' : 'Inactive'}
                  checked={details.isActive}
                  onChange={(checked) => updateField('isActive', checked)}
                />
              </div>
            </div>

            <div className="h-px w-full bg-border" />

            <div className="flex flex-col gap-4">
              <div className="flex w-full items-center justify-between">
                <p className="font-body text-sm font-semibold text-text-muted">Floors</p>
                {isEditMode && (
                  <button
                    type="button"
                    onClick={openAddFloorModal}
                    className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
                  >
                    <PlusIcon className="size-4" />
                    Add Floor
                  </button>
                )}
              </div>

              {isEditMode ? (
                <div className="flex flex-col gap-3">
                  {floors.map((floor) => (
                    <FloorCard
                      key={floor.id}
                      floor={floor}
                      departments={departments.filter((department) => department.floorId === floor.id)}
                      isExpanded={expandedFloorIds.has(floor.id)}
                      onToggleExpand={() => toggleFloorExpanded(floor.id)}
                      onEdit={() => openEditFloorModal(floor)}
                      onDelete={() => requestDeleteFloor(floor)}
                    />
                  ))}
                </div>
              ) : (
                <p className="font-body text-sm text-text-faint">Save this building first to start adding floors.</p>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
              <button type="button" onClick={cancel} className="rounded-full border border-border bg-surface px-6 py-2.5 font-body text-sm font-semibold text-text">
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void submit()}
                disabled={isSaving}
                className="rounded-full bg-admin-accent px-6 py-2.5 font-body text-sm font-semibold text-white disabled:opacity-50"
              >
                {isSaving ? 'Saving…' : isEditMode ? 'Save Changes' : 'Save Building'}
              </button>
            </div>
          </div>
        )}
      </div>

      <FloorModal
        isOpen={floorModal !== undefined}
        initialFloor={floorModal?.mode === 'edit' ? floorModal.floor : undefined}
        isSaving={isSavingFloor}
        onSave={(details) => void saveFloor(details)}
        onClose={closeFloorModal}
      />

      <ConfirmDialog
        isOpen={pendingDeleteFloor !== undefined}
        title="Delete Floor"
        message={`Are you sure you want to delete "${pendingDeleteFloor?.name}"? This cannot be undone.`}
        confirmLabel={isDeletingFloor ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDeleteFloor()}
        onCancel={cancelDeleteFloor}
      />
    </>
  )
}
