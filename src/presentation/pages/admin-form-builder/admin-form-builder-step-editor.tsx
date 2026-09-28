import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { LayersIcon, LockIcon, PlusIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingState } from '../../components/ui/LoadingState'
import { PageContentLayout } from '../../components/PageContentLayout'
import { usePageHeader } from '../../context/page-header-context'
import { AddFieldModal } from './Components/AddFieldModal'
import { CreateGroupModal } from './Components/CreateGroupModal'
import { FieldPropertiesPanel } from './Components/FieldPropertiesPanel'
import { GroupCard } from './Components/GroupCard'
import { SortableFieldRow } from './Components/SortableFieldRow'
import { SortableGroupCard } from './Components/SortableGroupCard'
import { useAdminFormBuilderStepEditor } from './hooks/use-admin-form-builder-step-editor'

export function AdminFormBuilderStepEditorPage() {
  const {
    step,
    fields,
    groups,
    selectedField,
    selectField,
    isLoading,
    errorMessage,
    retry,
    toggleFieldRequired,
    saveFieldProperties,
    assignFieldGroup,
    pendingDelete,
    requestDeleteField,
    cancelDeleteField,
    confirmDeleteField,
    isAddFieldOpen,
    openAddField,
    closeAddField,
    createField,
    reorderFields,
    isAddGroupOpen,
    openAddGroup,
    closeAddGroup,
    createGroup,
    saveGroupProperties,
    pendingDeleteGroup,
    requestDeleteGroup,
    cancelDeleteGroup,
    confirmDeleteGroup,
    reorderGroups,
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

  // Locked groups (the seeded "vehicles"/"visitors" groups) never get a drag
  // handle and stay out of the sortable list entirely — same convention as
  // `SortableStepCard`'s locked steps. Reordering only ever rearranges the
  // unlocked groups among themselves; locked groups keep their existing
  // position, which `reorderGroups` preserves by always listing them first
  // (matching how they're seeded — see `form_builder/defaults.py`).
  const lockedGroups = groups.filter((g) => g.isLocked)
  const unlockedGroups = groups.filter((g) => !g.isLocked)

  const handleGroupDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = unlockedGroups.findIndex((g) => g.id === active.id)
    const newIndex = unlockedGroups.findIndex((g) => g.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    const reordered = [...unlockedGroups]
    const [moved] = reordered.splice(oldIndex, 1)
    reordered.splice(newIndex, 0, moved)
    void reorderGroups([...lockedGroups.map((g) => g.id), ...reordered.map((g) => g.id)])
  }

  const fieldCountForGroup = (groupId: string): number => fields.filter((f) => f.groupId === groupId).length

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
            <div className="flex flex-col gap-6">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="font-display text-base font-bold text-text">Field Groups</h2>
                  <span className="font-body text-xs text-text-muted">Optional — repeatable if visitors can add multiple</span>
                </div>

                {lockedGroups.map((group) => (
                  <GroupCard
                    key={group.id}
                    group={group}
                    fieldCount={fieldCountForGroup(group.id)}
                    siblingFields={fields}
                    onSaveProperties={(input) => saveGroupProperties(group.id, input)}
                    onDelete={() => requestDeleteGroup(group)}
                  />
                ))}

                {unlockedGroups.length > 0 && (
                  <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleGroupDragEnd}>
                    <SortableContext items={unlockedGroups.map((g) => g.id)} strategy={verticalListSortingStrategy}>
                      <div className="flex flex-col gap-3">
                        {unlockedGroups.map((group) => (
                          <SortableGroupCard
                            key={group.id}
                            group={group}
                            fieldCount={fieldCountForGroup(group.id)}
                            siblingFields={fields}
                            onSaveProperties={(input) => saveGroupProperties(group.id, input)}
                            onDelete={() => requestDeleteGroup(group)}
                          />
                        ))}
                      </div>
                    </SortableContext>
                  </DndContext>
                )}

                <button
                  type="button"
                  onClick={openAddGroup}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-surface py-3 font-body text-sm font-semibold text-admin-accent"
                >
                  <LayersIcon className="size-4" />
                  Add Field Group
                </button>
              </div>

              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="font-display text-base font-bold text-text">Active Form Fields</h2>
                  <span className="font-body text-xs text-text-muted">Drag rows to reorder</span>
                </div>

                {/* "Location" isn't a real Form Builder field — it's hardcoded
                 * in the Visit Details step, always required, and populated
                 * from the Branches list rather than admin-typed options (see
                 * visitor-request/Components/steps/VisitInfoStep.tsx). Shown
                 * here read-only, purely so it's not invisible to admins
                 * comparing this list against the live form. */}
                {step?.key === 'visit_details' && (
                  <div className="flex items-center gap-3 rounded-xl border border-border bg-bg px-4 py-3 opacity-80">
                    <LockIcon className="size-3.5 shrink-0 text-text-faint" />
                    <div className="flex min-w-0 flex-1 flex-col gap-1">
                      <div className="flex items-center gap-3">
                        <span className="font-body text-sm font-semibold text-text">Location</span>
                        <span className="rounded-full bg-surface px-2 py-0.5 font-body text-[11px] font-medium text-text-muted">
                          Dropdown Select
                        </span>
                      </div>
                      <p className="font-body text-xs text-text-muted">
                        Always required. Populated from your Branches list — not configurable here.
                      </p>
                    </div>
                  </div>
                )}

                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                  <SortableContext items={fields.map((f) => f.id)} strategy={verticalListSortingStrategy}>
                    <div className="flex flex-col gap-2">
                      {fields.map((field, index) => {
                        const previousGroupId = index > 0 ? fields[index - 1].groupId : undefined
                        const group = field.groupId ? groups.find((g) => g.id === field.groupId) : undefined
                        return (
                          <div key={field.id} className="flex flex-col gap-2">
                            {field.groupId !== previousGroupId && (
                              <p className="mt-1 flex items-center gap-1.5 font-body text-[11px] font-bold tracking-wide text-text-faint uppercase">
                                {group ? (
                                  <>
                                    <LayersIcon className="size-3" />
                                    {group.name}
                                  </>
                                ) : (
                                  'Ungrouped'
                                )}
                              </p>
                            )}
                            <SortableFieldRow
                              field={field}
                              isSelected={field.id === selectedField?.id}
                              onSelect={() => selectField(field.id)}
                              onToggleRequired={() => void toggleFieldRequired(field)}
                              onDelete={() => requestDeleteField(field)}
                              groups={groups}
                              onAssignGroup={(groupId) => void assignFieldGroup(field.id, groupId)}
                            />
                          </div>
                        )
                      })}
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

      <AddFieldModal isOpen={isAddFieldOpen} onClose={closeAddField} onCreate={createField} />
      <CreateGroupModal isOpen={isAddGroupOpen} onClose={closeAddGroup} onCreate={(input) => void createGroup(input)} />

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Field"
        message={`Are you sure you want to delete "${pendingDelete?.label}"? This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => void confirmDeleteField()}
        onCancel={cancelDeleteField}
      />

      <ConfirmDialog
        isOpen={pendingDeleteGroup !== undefined}
        title="Delete Group"
        message={`Are you sure you want to delete the "${pendingDeleteGroup?.name}" group? Its fields will become ungrouped. This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => void confirmDeleteGroup()}
        onCancel={cancelDeleteGroup}
      />
    </PageContentLayout>
  )
}
