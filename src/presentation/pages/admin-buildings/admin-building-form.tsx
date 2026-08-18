import { AdminSidebar } from '../../components/AdminSidebar'
import { AdminTopBar } from '../../components/AdminTopBar'
import { ChevronLeftIcon, PlusIcon } from '../../components/icons'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { TextField } from '../../components/ui/TextField'
import { ToggleSwitch } from '../../components/ui/ToggleSwitch'
import { CheckpointModal } from './Components/CheckpointModal'
import { FloorCard } from './Components/FloorCard'
import { FloorModal } from './Components/FloorModal'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { useAdminBuildingForm } from './hooks/use-admin-building-form'

export function AdminBuildingFormPage() {
  const {
    isEditMode,
    currentUser,
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
    toggleFloorExpanded,
    openAddCheckpointModal,
    openEditCheckpointModal,
    closeCheckpointModal,
    checkpointModal,
    saveCheckpoint,
    requestDeleteCheckpoint,
    cancelDeleteCheckpoint,
    confirmDeleteCheckpoint,
    pendingDeleteCheckpoint,
    submit,
    cancel,
  } = useAdminBuildingForm()

  const branchOptions = branches.map((branch) => ({ value: branch.id, label: branch.name }))
  const fieldLabelClassName = 'text-[13px] font-semibold text-[#475569]'

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <AdminSidebar activeItem="buildings" />

      <div className="flex flex-1 flex-col">
        <AdminTopBar
          description="Administer branch premises, building access policies, and reception configurations"
          currentUser={currentUser}
        />

        <main className="flex flex-1 flex-col items-center p-8">
          <div className="flex w-full max-w-[1160px] flex-col gap-6">
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={cancel}
                aria-label="Back"
                className="flex size-9 items-center justify-center rounded-full border border-border bg-surface"
              >
                <ChevronLeftIcon className="size-4" />
              </button>
              <h1 className="font-display text-2xl font-bold text-text">{isEditMode ? 'Edit Building' : 'Add Building'}</h1>
            </div>

            {errorMessage ? (
              <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-border bg-surface p-12 text-center">
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
                  <div className="flex gap-6">
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
                  <TextField
                    label="Street Address"
                    value={details.streetAddress ?? ''}
                    onChange={(streetAddress) => updateField('streetAddress', streetAddress)}
                    labelClassName={fieldLabelClassName}
                  />
                  <div className="flex items-center justify-between py-2">
                    <div className="flex flex-col gap-1">
                      <p className="font-body text-sm font-semibold text-text-muted">Building Status</p>
                      <p className="font-body text-xs text-text-faint">Set active state to allow access allocation and visitor intake checks</p>
                    </div>
                    <ToggleSwitch
                      label={details.status === 'active' ? 'Active' : 'Inactive'}
                      checked={details.status === 'active'}
                      onChange={(checked) => updateField('status', checked ? 'active' : 'inactive')}
                    />
                  </div>
                </div>

                <div className="h-px w-full bg-border" />

                <div className="flex flex-col gap-4">
                  <div className="flex w-full items-center justify-between">
                    <p className="font-body text-sm font-semibold text-text-muted">Floors</p>
                    <button
                      type="button"
                      onClick={openAddFloorModal}
                      className="flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-2.5 font-body text-[13px] font-semibold text-text"
                    >
                      <PlusIcon className="size-4" />
                      Add Floor
                    </button>
                  </div>

                  <div className="flex flex-col gap-3">
                    {floors.map((floor) => (
                      <FloorCard
                        key={floor.id}
                        floor={floor}
                        isExpanded={expandedFloorIds.has(floor.id)}
                        onToggleExpand={() => toggleFloorExpanded(floor.id)}
                        onEdit={() => openEditFloorModal(floor)}
                        onDelete={() => requestDeleteFloor(floor)}
                        onAddCheckpoint={() => openAddCheckpointModal(floor.id)}
                        onEditCheckpoint={(checkpoint) => openEditCheckpointModal(floor.id, checkpoint)}
                        onDeleteCheckpoint={(checkpoint) => requestDeleteCheckpoint(floor.id, checkpoint)}
                      />
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 border-t border-border pt-4">
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
        </main>
      </div>

      <FloorModal
        isOpen={floorModal !== undefined}
        initialFloor={floorModal?.mode === 'edit' ? floorModal.floor : undefined}
        departments={departments}
        onSave={saveFloor}
        onClose={closeFloorModal}
      />

      <CheckpointModal
        isOpen={checkpointModal !== undefined}
        initialName={checkpointModal?.mode === 'edit' ? checkpointModal.checkpoint.name : undefined}
        onSave={saveCheckpoint}
        onClose={closeCheckpointModal}
      />

      <ConfirmDialog
        isOpen={pendingDeleteFloor !== undefined}
        title="Delete Floor"
        message={`Are you sure you want to delete "${pendingDeleteFloor?.name}"? Its checkpoints will be removed too.`}
        confirmLabel="Delete"
        onConfirm={confirmDeleteFloor}
        onCancel={cancelDeleteFloor}
      />

      <ConfirmDialog
        isOpen={pendingDeleteCheckpoint !== undefined}
        title="Delete Checkpoint"
        message={`Are you sure you want to delete "${pendingDeleteCheckpoint?.checkpoint.name}"?`}
        confirmLabel="Delete"
        onConfirm={confirmDeleteCheckpoint}
        onCancel={cancelDeleteCheckpoint}
      />
    </div>
  )
}
