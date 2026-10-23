import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

interface UseDropdownPanelOptions {
  count: number
  /** Index the highlight starts on when the panel opens. */
  getInitialIndex: () => number
  onSelect: (index: number) => void
  /** Lets a typed character jump to the next option starting with it. */
  getLabel?: (index: number) => string
  /** Close after `onSelect` (single-select) or stay open (multi-select). */
  closeOnSelect?: boolean
}

// Open/close, outside-click, highlight and keyboard handling shared by the
// themed dropdowns (single- and multi-select). The panel may render in a
// portal, so outside-click checks both the root and the panel.
export function useDropdownPanel({ count, getInitialIndex, onSelect, getLabel, closeOnSelect = false }: UseDropdownPanelOptions) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const listId = useId()

  useEffect(() => {
    if (!isOpen) return
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node
      if (!rootRef.current?.contains(target) && !panelRef.current?.contains(target)) setIsOpen(false)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [isOpen])

  useEffect(() => {
    if (isOpen) listRef.current?.focus({ preventScroll: true })
  }, [isOpen])

  const open = () => {
    setActiveIndex(Math.max(0, getInitialIndex()))
    setIsOpen(true)
  }

  const close = () => {
    setIsOpen(false)
    triggerRef.current?.focus()
  }

  const select = (index: number) => {
    onSelect(index)
    if (closeOnSelect) close()
  }

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (!isOpen && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      event.preventDefault()
      open()
    }
  }

  const handleListKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    if (count === 0) return
    if (event.key === 'Escape') {
      // Keep a surrounding modal from also treating this Escape as its own.
      event.preventDefault()
      event.stopPropagation()
      close()
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => (index + 1) % count)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => (index - 1 + count) % count)
    } else if (event.key === 'Home') {
      event.preventDefault()
      setActiveIndex(0)
    } else if (event.key === 'End') {
      event.preventDefault()
      setActiveIndex(count - 1)
    } else if (event.key === ' ' || event.key === 'Enter') {
      event.preventDefault()
      select(activeIndex)
    } else if (event.key === 'Tab') {
      setIsOpen(false)
    } else if (getLabel && event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const typed = event.key.toLowerCase()
      for (let step = 1; step <= count; step += 1) {
        const index = (activeIndex + step) % count
        if (getLabel(index).toLowerCase().startsWith(typed)) {
          setActiveIndex(index)
          break
        }
      }
    }
  }

  return {
    isOpen,
    setIsOpen,
    open,
    close,
    select,
    activeIndex,
    setActiveIndex,
    rootRef,
    panelRef,
    triggerRef,
    listRef,
    listId,
    handleTriggerKeyDown,
    handleListKeyDown,
  }
}
