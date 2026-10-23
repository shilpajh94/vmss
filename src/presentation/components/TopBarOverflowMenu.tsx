import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useRefreshContext } from '../context/refresh-context'
import { useThemeMode, type ThemeMode } from '../context/theme-mode-context'
import { CheckIcon, MonitorIcon, MoonIcon, MoreVerticalIcon, RefreshCcwIcon, SunIcon } from './icons'
import { ConfirmDialog } from './ui/ConfirmDialog'

const THEME_OPTIONS: ReadonlyArray<{ mode: ThemeMode; label: string; Icon: typeof SunIcon }> = [
  { mode: 'light', label: 'Light theme', Icon: SunIcon },
  { mode: 'dark', label: 'Dark theme', Icon: MoonIcon },
  { mode: 'system', label: 'System theme', Icon: MonitorIcon },
]

// Below `sm` the refresh and theme controls move in here, so the page title
// still fits a 360px top bar (responsive-layout). Same behaviour as the
// controls it stands in for: refresh asks first when a form has unsaved
// edits, and a dot marks a background refresh that is failing.
export function TopBarOverflowMenu() {
  const { activeRefresh } = useRefreshContext()
  const { mode, setMode } = useThemeMode()
  const [isOpen, setIsOpen] = useState(false)
  const [isConfirmingDiscard, setIsConfirmingDiscard] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    menuRef.current?.querySelector<HTMLButtonElement>('[role^="menuitem"]')?.focus()
    const handlePointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setIsOpen(false)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [isOpen])

  const close = (returnFocus: boolean) => {
    setIsOpen(false)
    if (returnFocus) buttonRef.current?.focus()
  }

  const onMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>('[role^="menuitem"]') ?? [])
    const index = items.findIndex((item) => item === document.activeElement)
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      items[(index + step + items.length) % items.length]?.focus()
    } else if (event.key === 'Escape' || event.key === 'Tab') {
      if (event.key === 'Escape') event.preventDefault()
      close(event.key === 'Escape')
    }
  }

  const refresh = () => {
    close(true)
    if (activeRefresh.hasUnsavedChanges) setIsConfirmingDiscard(true)
    else activeRefresh.refresh()
  }

  const itemClassName =
    'flex min-h-10 w-full items-center gap-3 px-3 text-left font-body text-sm text-text hover:bg-border-subtle focus-visible:bg-border-subtle focus-visible:outline-none'

  return (
    <div ref={containerRef} className="relative sm:hidden">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen((previous) => !previous)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label={activeRefresh.hasFailed ? 'More options (last refresh failed, retrying)' : 'More options'}
        className="relative flex size-10 items-center justify-center rounded-full border border-border bg-surface text-text"
      >
        <MoreVerticalIcon className="size-4" />
        {activeRefresh.hasFailed && <span aria-hidden className="absolute top-1.5 right-1.5 size-2 rounded-full bg-warning" />}
      </button>
      {isOpen && (
        <div
          ref={menuRef}
          role="menu"
          aria-label="More options"
          onKeyDown={onMenuKeyDown}
          className="absolute top-full right-0 z-40 mt-2 flex w-52 flex-col overflow-hidden rounded-xl border border-border bg-surface py-1 shadow-lg"
        >
          <button type="button" role="menuitem" onClick={refresh} className={itemClassName}>
            <RefreshCcwIcon className="size-4 shrink-0" />
            {activeRefresh.hasFailed ? "Refresh (couldn't refresh)" : 'Refresh'}
          </button>
          <div role="separator" className="my-1 h-px bg-border-subtle" />
          {THEME_OPTIONS.map(({ mode: optionMode, label, Icon }) => (
            <button
              key={optionMode}
              type="button"
              role="menuitemradio"
              aria-checked={mode === optionMode}
              onClick={() => {
                setMode(optionMode)
                close(true)
              }}
              className={itemClassName}
            >
              <Icon className="size-4 shrink-0" />
              <span className="flex-1">{label}</span>
              {mode === optionMode && <CheckIcon className="size-4 shrink-0 text-admin-accent" />}
            </button>
          ))}
        </div>
      )}
      <ConfirmDialog
        isOpen={isConfirmingDiscard}
        title="Discard unsaved changes?"
        message="Refreshing reloads this page's saved data. The changes you haven't saved will be lost."
        confirmLabel="Discard and refresh"
        onConfirm={() => {
          setIsConfirmingDiscard(false)
          activeRefresh.refresh()
        }}
        onCancel={() => setIsConfirmingDiscard(false)}
      />
    </div>
  )
}
