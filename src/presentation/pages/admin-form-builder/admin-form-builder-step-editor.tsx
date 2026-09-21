import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { PlusIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingState } from '../../components/ui/LoadingState'
import { PageContentLayout } from '../../components/PageContentLayout'
import { usePageHeader } from '../../context/page-header-context'
import { AddFieldModal } from './Components/AddFieldModal'
import { FieldPropertiesPanel } from './Components/FieldPropertiesPanel'
import { SortableFieldRow } from './Components/SortableFieldRow'
import { useAdminFormBuilderStepEditor } from './hooks/use-admin-form-builder-step-editor'

export function AdminFormBuilderStepEditorPage() {
  const {
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
    isPublishing,
    publish,
    hasUnpublishedChanges,
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

  usePageHeader({
    breadcrumb: [{ label: 'Form Builder' }, { label: step ? `${step.name} Fields` : 'Step Fields', isActive: true }],
  })

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="font-display text-2xl font-bold text-text">{step ? `${step.name} Step Editor` : 'Step Editor'}</h1>
              <button type="button" onClick={goBack} className="font-body text-sm text-admin-accent">
                ← Back to Form Builder
              </button>
            </div>
            <button
              type="button"
              onClick={() => void publish()}
              disabled={isPublishing}
              className="rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white disabled:opacity-60"
            >
              {isPublishing ? 'Publishing…' : 'Publish Changes'}
            </button>
          </div>

          {hasUnpublishedChanges && (
            <p className="rounded-lg bg-warning/15 px-4 py-2 font-body text-[13px] font-medium text-warning">
              You have unpublished changes. Visitors won't see them until you publish.
            </p>
          )}
        </>
      }
    >
      <div className="h-full min-h-0 overflow-y-auto scrollbar-thin">
        {errorMessage ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
            <p className="font-body text-sm text-danger">{errorMessage}</p>
            <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
              Try again
            </button>
          </div>
        ) : isLoading ? (
          <LoadingState label="Loading step fields…" className="h-full" />
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
                onSave={(input) => saveFieldProperties(selectedField.id, input)}
              />
            )}
          </div>
        )}
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
    </PageContentLayout>
  )
}
