import { DndContext, MouseSensor, TouchSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable'
import { PlusIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { SelectField } from '../../components/ui/SelectField'
import { PAGE_HEADER_GAP_CANCEL, PageContentLayout } from '../../components/PageContentLayout'
import { AsyncRegion } from '../../components/AsyncRegion'
import { Collapsible } from '../../components/ui/Collapsible'
import { CardGridSkeleton } from '../../components/ui/Skeleton'
import { PendingButton } from '../../components/ui/PendingButton'
import { PRESS_FEEDBACK_CLASS } from '../../components/ui/interactive'
import { usePageHeader } from '../../context/page-header-context'
import { CreateStepModal } from './Components/CreateStepModal'
import { SortableStepCard } from './Components/SortableStepCard'
import { StepCard } from './Components/StepCard'
import { DEFAULT_WORKSPACE_VALUE, useAdminFormBuilder } from './hooks/use-admin-form-builder'
import type { FormStep } from '../../../domain/entities/form-builder-schema'

// Mirrors `VMSS_API/src/vmss_api/form_builder/service.py`'s
// `_LEADING_LOCKED_KEYS`/`_TRAILING_LOCKED_KEYS` - the fixed, permanent
// identity of the three locked steps (no endpoint lets an admin create a
// new locked step or flip `isLocked`).
const LEADING_LOCKED_KEYS = ['visitor_info', 'visit_details']
const TRAILING_LOCKED_KEYS = ['review_confirm']

/** Splits the (already order-sorted) step list into the locked leading run,
 * the freely-reorderable middle run, and the locked trailing run.
 *
 * Identifies locked steps by their fixed `key`, not by scanning for a
 * contiguous `isLocked` run from each end - a scan would misidentify a
 * locked step as "movable" if a scope is ever transiently out of order
 * (e.g. a stale client cache from before `fix-form-builder-step-order-and-ui-gaps`'s
 * backend repair ran), which is exactly what caused the "Something went
 * wrong reordering steps" bug this hardens against. The backend's own
 * `create_step`/`_ensure_step_order_valid` are what actually guarantee the
 * order stays correct - this is defense in depth, not a substitute.
 */
function partitionSteps(steps: FormStep[]): {
  leading: FormStep[]
  movable: FormStep[]
  trailing: FormStep[]
} {
  const leading = LEADING_LOCKED_KEYS.flatMap((key) => steps.filter((s) => s.key === key))
  const trailing = TRAILING_LOCKED_KEYS.flatMap((key) => steps.filter((s) => s.key === key))
  const lockedIds = new Set([...leading, ...trailing].map((s) => s.id))
  const movable = steps.filter((s) => !lockedIds.has(s.id))
  return { leading, movable, trailing }
}

export function AdminFormBuilderPage() {
  const {
    branches,
    selectedBranchId,
    selectWorkspace,
    steps,
    phase,
    isRefreshing,
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
    reorderSteps,
    goToEditFields,
    isPublishing,
    publish,
    hasUnpublishedChanges,
  } = useAdminFormBuilder()

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 4 } }),
    // Press-and-hold, so a finger swipe still scrolls the page instead of
    // starting a drag (responsive-layout "Reordering form fields by touch").
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
  )
  const { leading, movable, trailing } = partitionSteps(steps)

  const handleStepDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = movable.findIndex((s) => s.id === active.id)
    const newIndex = movable.findIndex((s) => s.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    const reorderedMovable = [...movable]
    const [moved] = reorderedMovable.splice(oldIndex, 1)
    reorderedMovable.splice(newIndex, 0, moved)
    const fullOrder = [...leading, ...reorderedMovable, ...trailing].map((s) => s.id)
    void reorderSteps(fullOrder)
  }

  usePageHeader({ description: 'Customize your visitor registration workflows' })

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="font-display text-xl font-bold md:text-2xl text-text">Form Builder</h1>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="w-full sm:w-64">
                <SelectField
                  label=""
                  value={selectedBranchId ?? DEFAULT_WORKSPACE_VALUE}
                  onChange={selectWorkspace}
                  placeholderSelectable
                  placeholder="Tenant Default"
                  options={branches.map((branch) => ({ value: branch.id, label: branch.name }))}
                />
              </div>
              <button
                type="button"
                onClick={openCreateStep}
                className={`flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-admin-accent hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`}
              >
                <PlusIcon className="size-3.5" />
                Create Registration Step
              </button>
              <PendingButton
                onClick={() => void publish()}
                pending={isPublishing}
                pendingLabel="Publishing…"
                className="rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white hover:bg-admin-accent/90 disabled:opacity-60"
              >
                Publish Changes
              </PendingButton>
            </div>
          </div>

          <Collapsible open={hasUnpublishedChanges} closedClassName={PAGE_HEADER_GAP_CANCEL}>
            <p className="rounded-lg bg-warning/15 px-4 py-2 font-body text-[13px] font-medium text-warning">
              You have unpublished changes. Visitors won't see them until you publish.
            </p>
          </Collapsible>

          <h2 className="font-display text-lg font-bold text-text">Registration Steps</h2>
        </>
      }
    >
      <div className="flex h-full min-h-0 flex-col overflow-y-auto scrollbar-thin">
        <AsyncRegion
          phase={phase}
          isRefreshing={isRefreshing}
          skeleton={<CardGridSkeleton count={6} className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3" cardClassName="h-14" label="Loading registration steps…" />}
          errorMessage="Something went wrong loading the registration steps. Please try again."
          onRetry={retry}
          isEmpty={steps.length === 0}
          empty={
            <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
              <EmptyState message="No registration steps yet." />
            </div>
          }
        >
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {leading.map((step, index) => (
              <StepCard
                key={step.id}
                step={step}
                order={index + 1}
                onToggleActive={() => void toggleStepActive(step)}
                onEditFields={() => goToEditFields(step)}
                onDelete={() => requestDeleteStep(step)}
              />
            ))}
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleStepDragEnd}>
              <SortableContext items={movable.map((s) => s.id)} strategy={rectSortingStrategy}>
                {movable.map((step, index) => (
                  <SortableStepCard
                    key={step.id}
                    step={step}
                    order={leading.length + index + 1}
                    onToggleActive={() => void toggleStepActive(step)}
                    onEditFields={() => goToEditFields(step)}
                    onDelete={() => requestDeleteStep(step)}
                  />
                ))}
              </SortableContext>
            </DndContext>
            {trailing.map((step, index) => (
              <StepCard
                key={step.id}
                step={step}
                order={leading.length + movable.length + index + 1}
                onToggleActive={() => void toggleStepActive(step)}
                onEditFields={() => goToEditFields(step)}
                onDelete={() => requestDeleteStep(step)}
              />
            ))}
          </div>
        </AsyncRegion>
      </div>

      <CreateStepModal isOpen={isCreateOpen} onClose={closeCreateStep} onCreate={(name) => void createStep(name)} />

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Remove Registration Step"
        message={`Are you sure you want to remove "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel="Remove"
        onConfirm={() => void confirmDeleteStep()}
        onCancel={cancelDeleteStep}
      />
    </PageContentLayout>
  )
}
