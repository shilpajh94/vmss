import { useEffect, useRef } from 'react'
import { DndContext, MouseSensor, TouchSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { LayersIcon, LockIcon, PlusIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { PAGE_HEADER_GAP_CANCEL, PageContentLayout } from '../../components/PageContentLayout'
import { AsyncRegion } from '../../components/AsyncRegion'
import { Collapsible } from '../../components/ui/Collapsible'
import { FormSkeleton, ListSkeleton, Skeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
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
    setIsPanelDirty,
    panelScrollRequest,
    phase,
    isRefreshing,
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

  const panelRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (panelScrollRequest === 0) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    panelRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
  }, [panelScrollRequest])

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 4 } }),
    // Press-and-hold, so a finger swipe still scrolls the page instead of
    // starting a drag (responsive-layout "Reordering form fields by touch").
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
  )

  // Location / Building are always shown as locked, read-only rows on the
  // Visit Details step (populated from Branches / Buildings), even when the
  // backend also returns them as real fields — those are kept out of the
  // editable list so they can't be edited, reordered or deleted here.
  const LOCKED_VISIT_FIELDS = [
    { key: 'location', label: 'Location', description: 'Always required. Populated from your Branches list — not configurable here.' },
    { key: 'building', label: 'Building', description: 'Populated from your Buildings list for the selected location — not configurable here.' },
  ]
  const isLockedVisitField = (f: { key: string; label?: string }) =>
    step?.key === 'visit_details' &&
    LOCKED_VISIT_FIELDS.some((i) => i.key === f.key || f.label?.trim().toLowerCase() === i.label.toLowerCase())
  const editableFields = fields.filter((f) => !isLockedVisitField(f))
  const hiddenFieldIds = fields.filter(isLockedVisitField).map((f) => f.id)

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = editableFields.findIndex((f) => f.id === active.id)
    const newIndex = editableFields.findIndex((f) => f.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    const reordered = [...editableFields]
    const [moved] = reordered.splice(oldIndex, 1)
    reordered.splice(newIndex, 0, moved)
    void reorderFields([...hiddenFieldIds, ...reordered.map((f) => f.id)])
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
              <h1 className="font-display text-xl font-bold md:text-2xl text-text">{step ? `${step.name} Step Editor` : 'Step Editor'}</h1>
              <button type="button" onClick={goBack} className="font-body text-sm text-admin-accent">
                ← Back to Form Builder
              </button>
            </div>
            <PendingButton
              onClick={() => void publish()}
              pending={isPublishing}
              pendingLabel="Publishing…"
              className="rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-on-accent hover:bg-admin-accent/90 disabled:opacity-60"
            >
              Publish Changes
            </PendingButton>
          </div>

          <Collapsible open={hasUnpublishedChanges} closedClassName={PAGE_HEADER_GAP_CANCEL}>
            <p className="rounded-lg bg-warning/15 px-4 py-2 font-body text-[13px] font-medium text-warning">
              You have unpublished changes. Visitors won't see them until you publish.
            </p>
          </Collapsible>
        </>
      }
    >
      <div className="flex h-full min-h-0 flex-col overflow-y-auto scrollbar-thin">
        <AsyncRegion
          phase={phase}
          isRefreshing={isRefreshing}
          skeleton={
            // Same two-column layout as the editor: field groups + field rows
            // on the left, the properties panel on the right (lg and up).
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
              <div className="flex flex-col gap-6">
                <div className="flex flex-col gap-3">
                  <Skeleton className="h-4.5 w-28" />
                  <Skeleton className="h-28 w-full rounded-xl" />
                  <Skeleton className="h-12 w-full rounded-xl" />
                </div>
                <div className="flex flex-col gap-3">
                  <Skeleton className="h-4.5 w-36" />
                  <ListSkeleton rows={4} label="Loading step fields…" />
                </div>
              </div>
              <FormSkeleton rows={5} columns={1} className="max-lg:hidden" label="Loading field properties…" />
            </div>
          }
          errorMessage="Something went wrong loading this step. Please try again."
          onRetry={retry}
        >
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

                {/* "Location" and "Building" aren't real Form Builder fields — they're
                 * hardcoded in the Visit Details step and populated from the
                 * Branches / Buildings lists rather than admin-typed options (see
                 * visitor-request/Components/steps/VisitInfoStep.tsx). Shown
                 * here read-only, purely so they're not invisible to admins
                 * comparing this list against the live form. Skipped for any
                 * key the backend already returns as a real field, otherwise
                 * the same row shows up twice. */}
                {step?.key === 'visit_details' &&
                  LOCKED_VISIT_FIELDS
                    .map((item) => (
                    <div key={item.label} className="flex items-center gap-3 rounded-xl border border-border bg-bg px-4 py-3 opacity-80">
                      <LockIcon className="size-3.5 shrink-0 text-text-faint" />
                      <div className="flex min-w-0 flex-1 flex-col gap-1">
                        <div className="flex items-center gap-3">
                          <span className="font-body text-sm font-semibold text-text">{item.label}</span>
                          <span className="rounded-full bg-surface px-2 py-0.5 font-body text-[11px] font-medium text-text-muted">
                            Dropdown Select
                          </span>
                        </div>
                        <p className="font-body text-xs text-text-muted">{item.description}</p>
                      </div>
                    </div>
                  ))}

                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                  <SortableContext items={editableFields.map((f) => f.id)} strategy={verticalListSortingStrategy}>
                    <div className="flex flex-col gap-2">
                      {editableFields.map((field, index) => {
                        const previousGroupId = index > 0 ? editableFields[index - 1].groupId : undefined
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
              <div ref={panelRef} className="scroll-mb-4">
                <FieldPropertiesPanel
                  field={selectedField}
                  siblingFields={fields}
                  onSave={(input) => saveFieldProperties(selectedField.id, input)}
                  onDirtyChange={setIsPanelDirty}
                />
              </div>
            )}
          </div>
        </AsyncRegion>
      </div>

      <AddFieldModal isOpen={isAddFieldOpen} onClose={closeAddField} onCreate={createField} />
      <CreateGroupModal isOpen={isAddGroupOpen} onClose={closeAddGroup} onCreate={createGroup} />

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
