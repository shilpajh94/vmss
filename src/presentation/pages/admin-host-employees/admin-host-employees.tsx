import { useNavigate } from 'react-router'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { EmptyState } from '../../components/ui/EmptyState'
import { SelectField } from '../../components/ui/SelectField'
import { Pagination } from '../../components/Pagination'
import { PAGE_HEADER_GAP_CANCEL, PageContentLayout } from '../../components/PageContentLayout'
import { AsyncRegion } from '../../components/AsyncRegion'
import { Collapsible } from '../../components/ui/Collapsible'
import { TableSkeleton } from '../../components/ui/Skeleton'
import { PRESS_FEEDBACK_CLASS } from '../../components/ui/interactive'
import { usePageHeader } from '../../context/page-header-context'
import { HostEmployeesTable } from './Components/HostEmployeesTable'
import { useAdminHostEmployees } from './hooks/use-admin-host-employees'

export function AdminHostEmployeesPage() {
  const navigate = useNavigate()
  const {
    hostEmployees,
    total,
    page,
    pageSize,
    goToNextPage,
    goToPrevPage,
    departmentNameById,
    phase,
    isRefreshing,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    departments,
    roleOptions,
    departmentFilter,
    setDepartmentFilter,
    roleFilter,
    setRoleFilter,
    statusFilter,
    setStatusFilter,
    clearFilters,
    isFiltering,
  } = useAdminHostEmployees()

  usePageHeader({ description: 'Registry of employees authorized to sponsor and host corporate visitors' })

  const goToAddHostEmployee = () => navigate('/admin/host-employees/new')

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full flex-wrap items-center justify-between gap-3">
            <h1 className="font-display text-xl font-bold md:text-2xl text-text">Employees Directory</h1>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={toggleFilterPanel}
                aria-expanded={isFilterPanelOpen}
                className={`flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`}
              >
                <SlidersIcon className="size-3.5" />
                Filters
              </button>
              <button
                type="button"
                className={`flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text hover:bg-border-subtle ${PRESS_FEEDBACK_CLASS}`}
              >
                <PlusIcon className="size-3.5" />
                Import Hosts
              </button>
              <button
                type="button"
                onClick={goToAddHostEmployee}
                className={`flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-on-accent hover:bg-admin-accent/90 ${PRESS_FEEDBACK_CLASS}`}
              >
                <PlusIcon className="size-3.5" />
                Add Employee
              </button>
            </div>
          </div>

          <Collapsible open={isFilterPanelOpen} closedClassName={PAGE_HEADER_GAP_CANCEL}>
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-full sm:w-48">
                <SelectField
                  label="Department"
                  value={departmentFilter}
                  onChange={setDepartmentFilter}
                  placeholder="All"
                  options={departments.map((department) => ({ value: department.id, label: department.name }))}
                />
              </div>
              <div className="w-full sm:w-48">
                <SelectField
                  label="Role"
                  value={roleFilter}
                  onChange={setRoleFilter}
                  placeholder="All"
                  options={roleOptions.map((role) => ({ value: role, label: role }))}
                />
              </div>
              <div className="w-full sm:w-48">
                <SelectField
                  label="Status"
                  value={statusFilter}
                  onChange={setStatusFilter}
                  placeholder="All"
                  options={[
                    { value: 'active', label: 'Active' },
                    { value: 'inactive', label: 'Inactive' },
                  ]}
                />
              </div>
              {isFiltering && (
                <button type="button" onClick={clearFilters} className="font-body text-[13px] font-semibold text-admin-accent">
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
        isRefreshing={isRefreshing}
        skeleton={<TableSkeleton columns={6} rows={pageSize} label="Loading host employees…" />}
        errorMessage="Something went wrong loading the employees. Please try again."
        onRetry={retry}
        isEmpty={hostEmployees.length === 0}
        empty={
          <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface py-16">
            {isFiltering ? (
              <EmptyState message="No employees match these filters." />
            ) : (
              <EmptyState message="No employees yet." action={{ label: 'Add Employee', onClick: goToAddHostEmployee }} />
            )}
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          <HostEmployeesTable hostEmployees={hostEmployees} departmentNameById={departmentNameById} />
          <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      </AsyncRegion>
    </PageContentLayout>
  )
}
