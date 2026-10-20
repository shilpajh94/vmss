import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { flushSync } from 'react-dom'
import { usePresence } from '../hooks/use-presence'
import { useThemeMode, type ThemeMode } from '../context/theme-mode-context'
import { CheckIcon, MonitorIcon, MoonIcon, SunIcon } from './icons'

const OPTIONS: ReadonlyArray<{ mode: ThemeMode; label: string; Icon: typeof SunIcon }> = [
  { mode: 'light', label: 'Light', Icon: SunIcon },
  { mode: 'dark', label: 'Dark', Icon: MoonIcon },
  { mode: 'system', label: 'System', Icon: MonitorIcon },
]

// Light / Dark / System (theme-mode spec). A menu of radio items: arrow keys
// move, Enter/Space choose, Escape or an outside click closes and focus
// returns to the button. Mirrors the notification bell's popover.
export function ThemeModeMenu() {
  const { mode, setMode } = useThemeMode()
  const [isOpen, setIsOpen] = useState(false)
  // Choosing an option closes the menu at once, without its exit animation,
  // so nothing animates over the theme switch (theme-mode "Menu does not
  // overlap the switch"). Escape / outside click keep the animated close.
  const [closedBySelection, setClosedBySelection] = useState(false)
  const popover = usePresence(isOpen)
  const containerRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([])
  const current = OPTIONS.find((option) => option.mode === mode) ?? OPTIONS[2]

  const close = (returnFocus: boolean) => {
    setIsOpen(false)
    if (returnFocus) buttonRef.current?.focus()
  }

  useEffect(() => {
    if (!isOpen) return
    // Focus the selected item when the menu opens.
    itemRefs.current[OPTIONS.findIndex((option) => option.mode === mode)]?.focus()
    const handlePointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setIsOpen(false)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
    // Only on open; moving focus between items must not re-run this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  const onMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = itemRefs.current.findIndex((item) => item === document.activeElement)
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      itemRefs.current[(index + step + OPTIONS.length) % OPTIONS.length]?.focus()
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault()
      itemRefs.current[event.key === 'Home' ? 0 : OPTIONS.length - 1]?.focus()
    } else if (event.key === 'Escape' || event.key === 'Tab') {
      if (event.key === 'Escape') event.preventDefault()
      close(event.key === 'Escape')
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => {
          setClosedBySelection(false)
          setIsOpen((previous) => !previous)
        }}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label={`Theme: ${current.label}`}
        title={`Theme: ${current.label}`}
        className="flex size-10 items-center justify-center rounded-full border border-border bg-surface text-text lg:size-8"
      >
        <current.Icon className="size-3.5" />
      </button>
      {popover.isMounted && !(closedBySelection && !isOpen) ? (
        <div
          role="menu"
          aria-label="Theme"
          data-state={popover.state}
          onAnimationEnd={popover.onAnimationEnd}
          onKeyDown={onMenuKeyDown}
          className="motion-popover absolute top-12 right-0 z-50 flex w-40 origin-top-right flex-col gap-0.5 rounded-lg border border-border bg-surface p-1 shadow-[0_8px_24px_rgba(15,23,42,0.12)] lg:top-10"
        >
          {OPTIONS.map(({ mode: option, label, Icon }, index) => {
            const isSelected = option === mode
            return (
              <button
                key={option}
                ref={(element) => {
                  itemRefs.current[index] = element
                }}
                type="button"
                role="menuitemradio"
                aria-checked={isSelected}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => {
                  // Gone from the DOM before the switch captures the page.
                  flushSync(() => {
                    setClosedBySelection(true)
                    setIsOpen(false)
                  })
                  buttonRef.current?.focus()
                  setMode(option)
                }}
                className={`flex h-9 items-center gap-2.5 rounded-md px-2.5 text-left font-body text-sm font-medium focus-visible:outline-2 focus-visible:outline-admin-accent ${
                  isSelected ? 'bg-admin-accent/10 text-text' : 'text-text-muted hover:bg-border-subtle hover:text-text'
                }`}
              >
                <Icon className="size-4 shrink-0" />
                <span className="flex-1">{label}</span>
                {isSelected ? <CheckIcon className="size-4 shrink-0 text-admin-accent" /> : null}
              </button>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
