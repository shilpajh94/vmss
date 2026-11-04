import { useNavigate } from 'react-router'
import { AsyncRegion } from '../../components/AsyncRegion'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { Pagination } from '../../components/Pagination'
import { PAGE_HEADER_GAP_CANCEL, PageContentLayout } from '../../components/PageContentLayout'
import { Collapsible } from '../../components/ui/Collapsible'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { PRESS_FEEDBACK_CLASS } from '../../components/ui/interactive'
import { SelectField } from '../../components/ui/SelectField'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { usePageHeader } from '../../context/page-header-context'
import { ZonesTable } from './Components/ZonesTable'
import { useAdminZones, ZONE_SORT_OPTIONS } from './hooks/use-admin-zones'

export function AdminZonesPage() {
  const navigate = useNavigate()
  const zonesPage = useAdminZones()
  const { zones, total, page, pageSize, phase, canManage, isFiltering, isFeatureOff } = zonesPage

  usePageHeader({ description: 'Define the zones visitors can be granted access to and the gates that lead into them' })

  const goToAddZone = () => navigate('/admin/zones/new')

  const pagination =
    phase === 'ready' && zones.length > 0 ? (
      <div className="flex-none">
        <Pagination page={page} pageSize={pageSize} total={total} onPrev={zonesPage.goToPrevPage} onNext={zonesPage.goToNextPage} />
      </div>
    ) : undefined

  return (
    <PageContentLayout
      fitBody={zones.length > 0}
      footer={pagination}
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Zones</h1>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={zonesPage.toggleFilterPanel}
                aria-expanded={zonesPage.isFilterPanelOpen}
                className={`flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`}
              >
                <SlidersIcon className="size-3.5" />
                Filters
              </button>
              {canManage && (
                <button
                  type="button"
                  onClick={goToAddZone}
                  className={`flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-on-accent hover:bg-admin-accent/90 ${PRESS_FEEDBACK_CLASS}`}
                >
                  <PlusIcon className="size-3.5" />
                  Add Zone
                </button>
              )}
            </div>
          </div>

          <Collapsible open={zonesPage.isFilterPanelOpen} closedClassName={PAGE_HEADER_GAP_CANCEL}>
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-full sm:w-48">
                <SelectField label="Branch" value={zonesPage.branchFilter} onChange={zonesPage.setBranchFilter} placeholder="All" options={zonesPage.branchOptions} />
              </div>
              <div className="w-full sm:w-48">
                <SelectField
                  label="Status"
                  value={zonesPage.statusFilter}
                  onChange={zonesPage.setStatusFilter}
                  placeholder="All"
                  options={[
                    { value: 'active', label: 'Active' },
                    { value: 'inactive', label: 'Inactive' },
                  ]}
                />
              </div>
              <div className="w-full sm:w-48">
                <SelectField label="Sort by" value={zonesPage.sort} onChange={zonesPage.setSort} options={ZONE_SORT_OPTIONS} />
              </div>
              {isFiltering && (
                <button type="button" onClick={zonesPage.clearFilters} className="font-body text-[13px] font-semibold text-admin-accent">
                  Clear filters
                </button>
              )}
            </div>
          </Collapsible>
        </>
      }
    >
      <AsyncRegion
        phase={phase}
        isRefreshing={zonesPage.isRefreshing}
        skeleton={<TableSkeleton columns={6} rows={pageSize} label="Loading zones…" />}
        errorMessage={
          isFeatureOff ? 'Zone access control is not enabled for this environment.' : 'Something went wrong loading the zones. Please try again.'
        }
        onRetry={isFeatureOff ? undefined : zonesPage.retry}
        isEmpty={zones.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            {isFiltering ? (
              <EmptyState message="No zones match these filters." />
            ) : (
              <EmptyState message="No zones yet." action={canManage ? { label: 'Add Zone', onClick: goToAddZone } : undefined} />
            )}
          </div>
        }
      >
        <ZonesTable zones={zones} names={zonesPage.names} canManage={canManage} onDelete={zonesPage.requestDelete} />
      </AsyncRegion>

      <ConfirmDialog
        isOpen={zonesPage.pendingDelete !== undefined}
        title="Delete Zone"
        message={`Are you sure you want to delete "${zonesPage.pendingDelete?.name}"? Visits mapped to it lose access to this zone.`}
        confirmLabel="Delete"
        isBusy={zonesPage.isDeleting}
        busyLabel="Deleting…"
        onConfirm={() => void zonesPage.confirmDelete()}
        onCancel={zonesPage.cancelDelete}
      />
    </PageContentLayout>
  )
}
