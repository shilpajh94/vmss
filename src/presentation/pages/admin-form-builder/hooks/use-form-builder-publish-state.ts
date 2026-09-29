import { useCallback, useEffect, useState } from 'react'

/** Per-scope "has unpublished draft changes" flag, shared between the Steps
 * overview page (`use-admin-form-builder.ts`) and the Step/Field Editor
 * page (`use-admin-form-builder-step-editor.ts`) so a field edited on one
 * page shows the same "unpublished changes" state and Publish action on the
 * other — the concrete bug this closes (design.md Decision 4).
 *
 * Deliberately plain module state, not a React Context: the two pages are
 * separate routes that fully mount/unmount on navigation, so there is no
 * cross-page re-render to coordinate — each page only needs to read the
 * current flag for its scope on mount and write to it on mutation/publish.
 * A page reload clears it, same as the admin had before this fix (no
 * indicator at all) — not a regression, see design.md Risks.
 */
const dirtyScopes = new Set<string>()

function scopeKey(branchId: string | undefined): string {
  return branchId ?? '__tenant_default__'
}

export function useFormBuilderPublishState(branchId: string | undefined): {
  hasUnpublishedChanges: boolean
  markDirty: () => void
  markPublished: () => void
} {
  const [hasUnpublishedChanges, setHasUnpublishedChanges] = useState(() => dirtyScopes.has(scopeKey(branchId)))

  useEffect(() => {
    setHasUnpublishedChanges(dirtyScopes.has(scopeKey(branchId)))
  }, [branchId])

  const markDirty = useCallback(() => {
    dirtyScopes.add(scopeKey(branchId))
    setHasUnpublishedChanges(true)
  }, [branchId])

  const markPublished = useCallback(() => {
    dirtyScopes.delete(scopeKey(branchId))
    setHasUnpublishedChanges(false)
  }, [branchId])

  return { hasUnpublishedChanges, markDirty, markPublished }
}
