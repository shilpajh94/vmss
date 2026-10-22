import { useEffect, useRef, useState } from 'react'
import { usePageRefresh } from '../context/refresh-context'
import { useUnsavedChanges } from './use-unsaved-changes'

interface FormPageRefreshOptions {
  // The user-editable values; compared against what the last load produced.
  values: unknown
  // True while the form's load is in flight. Each load that finishes makes
  // the values it left behind the new "saved" baseline.
  isLoading: boolean
  // Re-fetches the page's data and resets the form to it.
  reload: () => void
}

// Registers a create/edit form with the shared top-bar refresh control
// (live-data-refresh): forms never poll, and the control asks before a
// reload would discard unsaved edits. Forms start from their loaded (or
// initial, for a create form) values, so the baseline is whatever `values`
// holds when a load finishes.
export function useFormPageRefresh({ values, isLoading, reload }: FormPageRefreshOptions): void {
  const [savedValues, setSavedValues] = useState(values)
  const wasLoadingRef = useRef(isLoading)

  useEffect(() => {
    if (wasLoadingRef.current && !isLoading) {
      setSavedValues(values)
    }
    wasLoadingRef.current = isLoading
  }, [isLoading, values])

  const isDirty = useUnsavedChanges(savedValues, values)

  usePageRefresh({ refresh: reload, isRefreshing: isLoading, hasUnsavedChanges: !isLoading && isDirty })
}
