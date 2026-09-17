import { useNavigate } from 'react-router'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { Pagination } from '../../components/Pagination'
import { PageContentLayout } from '../../components/PageContentLayout'
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
    isLoading,
    errorMessage,
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
          <div className="flex w-full items-center justify-between">
            <h1 className="font-display text-2xl font-bold text-text">Employees Directory</h1>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={toggleFilterPanel}
                className="flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text"
              >
                <SlidersIcon className="size-3.5" />
                Filters
              </button>
              <button
                type="button"
                className="flex items-center gap-2 rounded-full border border-border bg-surface p-btn-secondary font-body text-[13px] font-semibold text-text"
              >
                <PlusIcon className="size-3.5" />
                Import Hosts
              </button>
              <button
                type="button"
                onClick={goToAddHostEmployee}
                className="flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white"
              >
                <PlusIcon className="size-3.5" />
                Add Employee
              </button>
            </div>
          </div>

          {isFilterPanelOpen && (
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-48">
                <SelectField
                  label="Department"
                  value={departmentFilter}
                  onChange={setDepartmentFilter}
                  placeholder="All"
                  options={departments.map((department) => ({ value: department.id, label: department.name }))}
                />
              </div>
              <div className="w-48">
                <SelectField
                  label="Role"
                  value={roleFilter}
                  onChange={setRoleFilter}
                  placeholder="All"
                  options={roleOptions.map((role) => ({ value: role, label: role }))}
                />
              </div>
              <div className="w-48">
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
          )}
        </>
      }
    >
      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-12 text-center">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading host employees…" className="flex-1" />
      ) : hostEmployees.length === 0 ? (
        <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
          {isFiltering ? (
            <EmptyState message="No employees match these filters." />
          ) : (
            <EmptyState message="No employees yet." action={{ label: 'Add Employee', onClick: goToAddHostEmployee }} />
          )}
        </div>
      ) : (
        <div className="flex h-full flex-col gap-3">
          <HostEmployeesTable hostEmployees={hostEmployees} departmentNameById={departmentNameById} />
          <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      )}
    </PageContentLayout>
  )
}
