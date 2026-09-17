import { useNavigate } from 'react-router'
import { PlusIcon, SlidersIcon } from '../../components/icons'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingState } from '../../components/ui/LoadingState'
import { SelectField } from '../../components/ui/SelectField'
import { Pagination } from '../../components/Pagination'
import { PageContentLayout } from '../../components/PageContentLayout'
import { usePageHeader } from '../../context/page-header-context'
import { SecurityGatesTable } from './Components/SecurityGatesTable'
import { useAdminSecurityGates } from './hooks/use-admin-security-gates'

export function AdminSecurityGatesPage() {
  const navigate = useNavigate()
  const {
    securityGates,
    total,
    page,
    pageSize,
    goToNextPage,
    goToPrevPage,
    isLoading,
    errorMessage,
    retry,
    isFilterPanelOpen,
    toggleFilterPanel,
    buildingOptions,
    buildingFilter,
    setBuildingFilter,
    gateTypeFilter,
    setGateTypeFilter,
    securityLevelFilter,
    setSecurityLevelFilter,
    clearFilters,
    isFiltering,
    pendingDelete,
    isDeleting,
    requestDelete,
    cancelDelete,
    confirmDelete,
  } = useAdminSecurityGates()

  usePageHeader({ description: 'Configure hardware gates, turnstiles, authentication protocols and connectivity status' })

  const goToRegisterGate = () => navigate('/admin/security-gates/new')

  return (
    <PageContentLayout
      header={
        <>
          <div className="flex w-full items-center justify-between">
            <h1 className="font-display text-2xl font-bold text-text">Security Gates & Turnstiles</h1>
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
                onClick={goToRegisterGate}
                className="flex items-center gap-2 rounded-full bg-admin-accent p-btn-primary font-body text-[13px] font-semibold text-white"
              >
                <PlusIcon className="size-3.5" />
                Register Gate
              </button>
            </div>
          </div>

          {isFilterPanelOpen && (
            <div className="flex w-full flex-wrap items-end gap-4 rounded-2xl border border-border bg-surface p-filter-panel">
              <div className="w-48">
                <SelectField label="Building" value={buildingFilter} onChange={setBuildingFilter} placeholder="All" options={buildingOptions} />
              </div>
              <div className="w-48">
                <SelectField
                  label="Gate Type"
                  value={gateTypeFilter}
                  onChange={setGateTypeFilter}
                  placeholder="All"
                  options={[
                    { value: 'entry', label: 'Entry Only' },
                    { value: 'exit', label: 'Exit Only' },
                    { value: 'both', label: 'Entry & Exit' },
                  ]}
                />
              </div>
              <div className="w-48">
                <SelectField
                  label="Security Level"
                  value={securityLevelFilter}
                  onChange={setSecurityLevelFilter}
                  placeholder="All"
                  options={[
                    { value: 'high', label: 'High Security' },
                    { value: 'standard', label: 'Standard' },
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
        <LoadingState label="Loading security gates…" className="flex-1" />
      ) : securityGates.length === 0 ? (
        <div className="flex w-full flex-1 items-center justify-center rounded-2xl border border-border bg-surface">
          {isFiltering ? (
            <EmptyState message="No security gates match these filters." />
          ) : (
            <EmptyState message="No security gates yet." action={{ label: 'Register Gate', onClick: goToRegisterGate }} />
          )}
        </div>
      ) : (
        <div className="flex h-full flex-col gap-3">
          <SecurityGatesTable securityGates={securityGates} onDelete={requestDelete} />
          <Pagination page={page} pageSize={pageSize} total={total} onPrev={goToPrevPage} onNext={goToNextPage} />
        </div>
      )}

      <ConfirmDialog
        isOpen={pendingDelete !== undefined}
        title="Delete Security Gate"
        message={`Are you sure you want to delete "${pendingDelete?.name}"? This cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting…' : 'Delete'}
        onConfirm={() => void confirmDelete()}
        onCancel={cancelDelete}
      />
    </PageContentLayout>
  )
}
