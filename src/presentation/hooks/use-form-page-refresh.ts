import { useEffect, useRef, useState } from 'react'
import { usePageRefresh } from '../context/refresh-context'
import { useUnsavedChanges } from './use-unsaved-changes'
import { useUnsavedChangesGuard } from './use-unsaved-changes-guard'

interface FormPageRefreshOptions {
  // The user-editable values; compared against what the last load produced.
  values: unknown
  // True while the form's load is in flight. Each load that finishes makes
  // the values it left behind the new "saved" baseline.
  isLoading: boolean
  // Re-fetches the page's data and resets the form to it.
  reload: () => void
  // A create form's empty values. Its load only fetches option lists and
  // leaves `values` alone, so the form can be typed into while it runs;
  // without a fixed baseline, that input would become the "saved" values
  // when the load finished and stop counting as unsaved (QA F13).
  baseline?: unknown
  // True once the form has been submitted (a wizard's success screen):
  // what it still holds is no longer unsaved.
  isComplete?: boolean
}

// Registers a create/edit form with the shared top-bar refresh control
// (live-data-refresh): forms never poll, and the control asks before a
// reload would discard unsaved edits. Edit forms start from their loaded
// values, so the baseline is whatever `values` holds when a load finishes.
//
// It also guards leaving the page with unsaved input (D-W6). Call `release()`
// right before navigating away after a successful save, and wrap an in-page
// discard (a Cancel that resets) in `confirmDiscard`.
export function useFormPageRefresh({ values, isLoading, reload, baseline, isComplete = false }: FormPageRefreshOptions) {
  const [loadedValues, setLoadedValues] = useState(values)
  const wasLoadingRef = useRef(isLoading)

  useEffect(() => {
    if (wasLoadingRef.current && !isLoading) {
      setLoadedValues(values)
    }
    wasLoadingRef.current = isLoading
  }, [isLoading, values])

  const savedValues = baseline === undefined ? loadedValues : baseline
  const isDirty = useUnsavedChanges(savedValues, values) && !isComplete
  // An edit form's values are only meaningful once loaded; a create form's
  // baseline is known up front.
  const hasUnsavedChanges = isDirty && (baseline !== undefined || !isLoading)

  usePageRefresh({ refresh: reload, isRefreshing: isLoading, hasUnsavedChanges })

  return useUnsavedChangesGuard(hasUnsavedChanges)
}
