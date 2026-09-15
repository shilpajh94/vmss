import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { AdminSidebar } from '../../components/AdminSidebar'
import { AdminTopBar } from '../../components/AdminTopBar'
import { PlusIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingState } from '../../components/ui/LoadingState'
import { AddFieldModal } from './Components/AddFieldModal'
import { FieldPropertiesPanel } from './Components/FieldPropertiesPanel'
import { SortableFieldRow } from './Components/SortableFieldRow'
import { useAdminFormBuilderStepEditor } from './hooks/use-admin-form-builder-step-editor'

export function AdminFormBuilderStepEditorPage() {
  const {
    currentUser,
    step,
    fields,
    selectedField,
    selectField,
    isLoading,
    errorMessage,
    retry,
    toggleFieldRequired,
    saveFieldProperties,
    pendingDelete,
    requestDeleteField,
    cancelDeleteField,
    confirmDeleteField,
    isAddFieldOpen,
    openAddField,
    closeAddField,
    createField,
    reorderFields,
    goBack,
  } = useAdminFormBuilderStepEditor()

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = fields.findIndex((f) => f.id === active.id)
    const newIndex = fields.findIndex((f) => f.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    const reordered = [...fields]
    const [moved] = reordered.splice(oldIndex, 1)
    reordered.splice(newIndex, 0, moved)
    void reorderFields(reordered.map((f) => f.id))
  }

  return (
    <div className="flex min-h-screen w-full items-stretch bg-bg">
      <AdminSidebar activeItem="form-builder" />

      <div className="flex flex-1 flex-col">
        <AdminTopBar
          breadcrumb={[
            { label: 'Form Builder' },
            { label: step ? `${step.name} Fields` : 'Step Fields', isActive: true },
          ]}
          currentUser={currentUser}
        />

        <main className="flex flex-1 flex-col gap-6 p-8">
          <div className="flex w-full items-center justify-between">
            <div>
              <h1 className="font-display text-2xl font-bold text-text">{step ? `${step.name} Step Editor` : 'Step Editor'}</h1>
              <button type="button" onClick={goBack} className="font-body text-sm text-admin-accent">
                ← Back to Form Builder
              </button>
            </div>
          </div>

          {errorMessage ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
              <p className="font-body text-sm text-danger">{errorMessage}</p>
              <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
                Try again
              </button>
            </div>
          ) : isLoading ? (
            <LoadingState label="Loading step fields…" className="flex-1" />
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="font-display text-base font-bold text-text">Active Form Fields</h2>
                  <span className="font-body text-xs text-text-muted">Drag rows to reorder</span>
                </div>

                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                  <SortableContext items={fields.map((f) => f.id)} strategy={verticalListSortingStrategy}>
                    <div className="flex flex-col gap-2">
                      {fields.map((field) => (
                        <SortableFieldRow
                          key={field.id}
                          field={field}
                          isSelected={field.id === selectedField?.id}
                          onSelect={() => selectField(field.id)}
                          onToggleRequired={() => void toggleFieldRequired(field)}
                          onDelete={() => requestDeleteField(field)}
                        />
                      ))}
                    </div>
                  </SortableContext>
                </DndContext>

                <button
                  type="button"
                  onClick={openAddField}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-surface py-4 font-body text-sm font-semibold text-admin-accent"
                >
                  <PlusIcon className="size-4" />
                  Add New Custom Field
                </button>
              </div>

              {selectedField && (
                <FieldPropertiesPanel
                  field={selectedField}
                  siblingFields={fields}
                  onSave={(input) => void saveFieldProperties(selectedField.id, input)}
                />
              )}
            </div>
          )}
        </main>
      </div>

      <AddFieldModal isOpen={isAddFieldOpen} onClose={closeAddField} onCreate={(input) => void createField(input)} />

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Field"
        message={`Are you sure you want to delete "${pendingDelete?.label}"? This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => void confirmDeleteField()}
        onCancel={cancelDeleteField}
      />
    </div>
  )
}
