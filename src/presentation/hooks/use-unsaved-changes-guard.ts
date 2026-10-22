import { useCallback, useEffect, useRef } from 'react'
import { useBlocker, type BlockerFunction } from 'react-router'
import { useUnsavedChangesContext } from '../context/unsaved-changes-context'

const SIGN_IN_PATHS = new Set(['/admin/login', '/staff/login'])

interface DiscardConfirm {
  // Lets the next navigation (or tab close) through unprompted: call it
  // right before navigating away after a successful save.
  release: () => void
  // Runs `proceed` straight away when nothing is unsaved, and otherwise only
  // once the user confirms discarding (closing a modal, switching fields,
  // a Cancel button that resets in place).
  confirmDiscard: (proceed: () => void) => void
}

// Protects unsaved input from being lost (app-shell "Unsaved Form Input Is
// Protected From Accidental Loss", design D-W6) without blocking router
// navigation: closing or reloading the tab gets the browser's own
// `beforeunload` prompt, and `confirmDiscard` asks before an in-page discard.
// This is the whole guard for a modal, which must not register a router
// blocker: the router honours only the most recently registered one, so a
// modal's would shadow the page's.
export function useDiscardConfirm(isDirty: boolean): DiscardConfirm & { isGuarding: () => boolean } {
  const { askToDiscard } = useUnsavedChangesContext()
  const isDirtyRef = useRef(isDirty)
  const releasedRef = useRef(false)
  isDirtyRef.current = isDirty

  useEffect(() => {
    // Clean again (saved, or edits undone): the next edit is guarded anew.
    if (!isDirty) {
      releasedRef.current = false
      return
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (releasedRef.current) return
      event.preventDefault()
      // Older browsers only prompt when `returnValue` is set.
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isDirty])

  const release = useCallback(() => {
    releasedRef.current = true
  }, [])

  const isGuarding = useCallback(() => isDirtyRef.current && !releasedRef.current, [])

  const confirmDiscard = useCallback(
    (proceed: () => void) => {
      if (!isGuarding()) {
        proceed()
        return
      }
      askToDiscard({ onDiscard: proceed, onStay: () => undefined })
    },
    [askToDiscard, isGuarding],
  )

  return { release, confirmDiscard, isGuarding }
}

// `useDiscardConfirm` plus the router blocker, for a form that is a page (or
// a wizard): in-app navigation and the browser back button ask first too.
// `isDirty` is the caller's comparison against its last-saved values.
export function useUnsavedChangesGuard(isDirty: boolean): DiscardConfirm {
  const { askToDiscard } = useUnsavedChangesContext()
  const { release, confirmDiscard, isGuarding } = useDiscardConfirm(isDirty)

  // A move to a sign-in page (session expired, signed out) isn't blocked:
  // the session is already gone, so staying couldn't save anything.
  const shouldBlock = useCallback<BlockerFunction>(
    ({ currentLocation, nextLocation }) =>
      isGuarding() &&
      !SIGN_IN_PATHS.has(nextLocation.pathname) &&
      (currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search),
    [isGuarding],
  )
  const blocker = useBlocker(shouldBlock)

  useEffect(() => {
    if (blocker.state !== 'blocked') return
    askToDiscard({ onDiscard: () => blocker.proceed(), onStay: () => blocker.reset() })
  }, [blocker, askToDiscard])

  return { release, confirmDiscard }
}
