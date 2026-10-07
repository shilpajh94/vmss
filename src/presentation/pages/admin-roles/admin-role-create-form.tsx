import { BackButton } from '../../components/BackButton'
import { Checkbox } from '../../components/ui/Checkbox'
import { LoadingState } from '../../components/ui/LoadingState'
import { usePageHeader } from '../../context/page-header-context'
import { useAdminRoleCreateForm } from './hooks/use-admin-role-create-form'

export function AdminRoleCreateFormPage() {
  const {
    permissions,
    name,
    setName,
    description,
    setDescription,
    selectedCodes,
    isLoading,
    errorMessage,
    nameError,
    retry,
    isSaving,
    togglePermission,
    submit,
    cancel,
  } = useAdminRoleCreateForm()

  usePageHeader({ breadcrumb: [{ label: 'Roles & Permissions' }, { label: 'Add Role', isActive: true }] })

  return (
    <>
      {errorMessage ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-border bg-surface p-6 text-center md:p-12">
          <p className="font-body text-sm text-danger">{errorMessage}</p>
          <button type="button" onClick={retry} className="rounded-lg bg-admin-accent px-4 py-2 font-body text-sm font-semibold text-white">
            Try again
          </button>
        </div>
      ) : isLoading ? (
        <LoadingState label="Loading permission catalog…" className="flex-1" />
      ) : (
        <>
          <div className="flex items-center gap-4">
            <BackButton onClick={cancel} />
            <div className="flex flex-col gap-1">
              <h1 className="font-display text-xl font-bold md:text-2xl text-text">Add Role</h1>
              <p className="font-body text-sm text-text-muted">Name the role and choose what it is permitted to do.</p>
            </div>
          </div>

          <div className="flex w-full flex-col gap-4 rounded-2xl border border-border bg-surface p-4 md:p-6">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="role-name" className="font-body text-sm font-semibold text-text">
                Role name
              </label>
              <input
                id="role-name"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="rounded-lg border border-border bg-bg px-3 py-2 font-body text-sm text-text"
                placeholder="e.g. Front Desk Supervisor"
              />
              {nameError ? <p className="font-body text-xs text-danger">{nameError}</p> : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="role-description" className="font-body text-sm font-semibold text-text">
                Description
              </label>
              <textarea
                id="role-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="rounded-lg border border-border bg-bg px-3 py-2 font-body text-sm text-text"
                placeholder="Optional"
                rows={2}
              />
            </div>
          </div>

          <div className="flex w-full flex-1 flex-col gap-3 rounded-2xl border border-border bg-surface p-4 md:p-6">
            {permissions.map((permission) => (
              <div key={permission.code} className="flex flex-col gap-0.5 border-b border-border-subtle pb-3 last:border-0 last:pb-0">
                <Checkbox checked={selectedCodes.has(permission.code)} onChange={(checked) => togglePermission(permission.code, checked)}>
                  <span className="font-body text-sm font-semibold text-text">{permission.code}</span>
                </Checkbox>
                <p className="pl-6 font-body text-xs text-text-muted">{permission.description}</p>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={cancel}
              className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isSaving}
              onClick={() => void submit()}
              className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-50"
            >
              {isSaving ? 'Creating…' : 'Create Role'}
            </button>
          </div>
        </>
      )}
    </>
  )
}
