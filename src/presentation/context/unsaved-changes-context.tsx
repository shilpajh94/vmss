import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'

interface DiscardRequest {
  onDiscard: () => void
  onStay: () => void
}

interface UnsavedChangesContextValue {
  // Shows the one shared "Discard unsaved changes?" dialog.
  askToDiscard: (request: DiscardRequest) => void
}

const UnsavedChangesContext = createContext<UnsavedChangesContextValue | undefined>(undefined)

// Hosts the confirmation that `useUnsavedChangesGuard` asks for, once, at the
// app root, so a guarded form doesn't have to render its own dialog. It
// renders after `children`, so it stacks above a modal that asked for it.
export function UnsavedChangesProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<DiscardRequest | undefined>(undefined)

  const askToDiscard = useCallback((next: DiscardRequest) => setRequest(next), [])
  const value = useMemo(() => ({ askToDiscard }), [askToDiscard])

  return (
    <UnsavedChangesContext.Provider value={value}>
      {children}
      <ConfirmDialog
        isOpen={request !== undefined}
        title="Discard unsaved changes?"
        message="You have changes that haven't been saved. If you leave now, they will be lost."
        confirmLabel="Discard changes"
        cancelLabel="Keep editing"
        onConfirm={() => {
          request?.onDiscard()
          setRequest(undefined)
        }}
        onCancel={() => {
          request?.onStay()
          setRequest(undefined)
        }}
      />
    </UnsavedChangesContext.Provider>
  )
}

export function useUnsavedChangesContext(): UnsavedChangesContextValue {
  const context = useContext(UnsavedChangesContext)
  if (!context) {
    throw new Error('useUnsavedChangesContext must be used within an UnsavedChangesProvider')
  }
  return context
}
