import { useLayoutEffect, useState } from 'react'
import type { ComponentType, CSSProperties, SVGProps } from 'react'
import { createPortal } from 'react-dom'
import { useDropdownPanel } from '../../hooks/use-dropdown-panel'
import { CheckIcon, ChevronDownIcon } from '../icons'

export interface DropdownOption {
  value: string
  label: string
}

interface SelectDropdownProps {
  options: DropdownOption[]
  value: string
  onChange: (value: string) => void
  ariaLabel: string
  /** `filter`: compact 40px pill with an icon. `field`: form input look. */
  variant?: 'filter' | 'field'
  icon?: ComponentType<SVGProps<SVGSVGElement>>
  /** Shown on the trigger while `value` matches no option (e.g. "Select"). */
  placeholder?: string
  /** Also list the placeholder as a choosable row with an empty value (e.g. "All branches"). */
  placeholderSelectable?: boolean
  disabled?: boolean
  error?: boolean
  required?: boolean
  id?: string
  className?: string
}

const PANEL_MAX_HEIGHT = 256
const PANEL_GAP = 6
const VIEWPORT_MARGIN = 8

// Themed replacement for the native <select>, matching MultiSelectFilter's
// trigger and panel. The panel renders in a portal at fixed coordinates so
// scrolling modals and overflow containers never clip it.
export function SelectDropdown({
  options,
  value,
  onChange,
  ariaLabel,
  variant = 'field',
  icon: Icon,
  placeholder = 'Select',
  placeholderSelectable = false,
  disabled = false,
  error = false,
  required,
  id,
  className = '',
}: SelectDropdownProps) {
  const rows: DropdownOption[] = placeholderSelectable ? [{ value: '', label: placeholder }, ...options] : options
  const selectedIndex = rows.findIndex((row) => row.value === value)
  const triggerLabel = selectedIndex >= 0 ? rows[selectedIndex].label : placeholder
  const [panelStyle, setPanelStyle] = useState<CSSProperties>()

  const { isOpen, open, close, select, activeIndex, setActiveIndex, rootRef, panelRef, triggerRef, listRef, listId, handleTriggerKeyDown, handleListKeyDown } =
    useDropdownPanel({
      count: rows.length,
      getInitialIndex: () => selectedIndex,
      onSelect: (index) => onChange(rows[index].value),
      getLabel: (index) => rows[index].label,
      closeOnSelect: true,
    })

  useLayoutEffect(() => {
    if (!isOpen) return
    const place = () => {
      const trigger = triggerRef.current?.getBoundingClientRect()
      if (!trigger) return
      const spaceBelow = window.innerHeight - trigger.bottom - VIEWPORT_MARGIN
      const spaceAbove = trigger.top - VIEWPORT_MARGIN
      const flip = spaceBelow < Math.min(PANEL_MAX_HEIGHT, 200) && spaceAbove > spaceBelow
      const width = Math.max(trigger.width, variant === 'filter' ? 220 : 0)
      const left = Math.min(Math.max(VIEWPORT_MARGIN, trigger.left), Math.max(VIEWPORT_MARGIN, window.innerWidth - width - VIEWPORT_MARGIN))
      setPanelStyle({
        left,
        minWidth: Math.min(width, window.innerWidth - VIEWPORT_MARGIN * 2),
        maxHeight: Math.min(PANEL_MAX_HEIGHT, Math.max(96, flip ? spaceAbove : spaceBelow) - PANEL_GAP),
        ...(flip ? { bottom: window.innerHeight - trigger.top + PANEL_GAP } : { top: trigger.bottom + PANEL_GAP }),
      })
    }
    place()
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [isOpen, triggerRef, variant])

  const isFilter = variant === 'filter'
  const triggerClass = isFilter
    ? `flex h-10 w-full items-center gap-2 rounded-lg border bg-surface px-3 hover:bg-surface-muted ${error ? 'border-danger' : 'border-border-strong'}`
    : `flex w-full items-center gap-2 rounded-lg border bg-surface px-3 py-2 text-left max-lg:min-h-10 ${error ? 'border-danger' : 'border-border'}`
  const labelClass = isFilter
    ? 'font-body text-[13px] font-semibold text-text max-sm:text-base'
    : 'text-body text-text max-sm:text-base'

  return (
    <div ref={rootRef} className={`relative ${isFilter ? 'w-full shrink-0 sm:w-[200px]' : 'w-full'} ${className}`}>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listId : undefined}
        aria-required={required}
        aria-invalid={error || undefined}
        onClick={() => (isOpen ? close() : open())}
        onKeyDown={handleTriggerKeyDown}
        className={`${triggerClass} transition-colors focus-visible:ring-2 focus-visible:ring-secondary-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60`}
      >
        {Icon ? <Icon className="size-4 shrink-0 text-text" /> : null}
        <span className={`min-w-0 flex-1 truncate text-left ${labelClass} ${selectedIndex < 0 || (placeholderSelectable && value === '' && !isFilter) ? 'text-text-muted' : ''}`}>
          {triggerLabel}
        </span>
        <ChevronDownIcon className={`size-4 shrink-0 text-text transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen
        ? createPortal(
            <div
              ref={panelRef}
              style={panelStyle}
              className="fixed z-[70] flex flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-lg"
            >
              <ul
                ref={listRef}
                id={listId}
                role="listbox"
                aria-label={ariaLabel}
                aria-activedescendant={`${listId}-${activeIndex}`}
                tabIndex={0}
                onKeyDown={handleListKeyDown}
                className="min-h-0 flex-1 overflow-y-auto p-1 focus:outline-none"
              >
                {rows.map((row, index) => {
                  const selected = index === selectedIndex
                  return (
                    <li
                      key={`${row.value}-${index}`}
                      id={`${listId}-${index}`}
                      role="option"
                      aria-selected={selected}
                      onClick={() => select(index)}
                      onMouseEnter={() => setActiveIndex(index)}
                      className={`flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 font-body text-[13px] text-text max-sm:py-2.5 max-sm:text-base ${
                        index === activeIndex ? 'bg-surface-muted' : ''
                      }`}
                    >
                      <span className={`min-w-0 flex-1 truncate ${selected ? 'font-semibold' : ''}`}>{row.label}</span>
                      {selected ? <CheckIcon aria-hidden="true" className="size-4 shrink-0 text-admin-accent" /> : null}
                    </li>
                  )
                })}
                {rows.length === 0 ? <li className="px-2.5 py-2 font-body text-[13px] text-text-muted">No options</li> : null}
              </ul>
            </div>,
            document.body,
          )
        : null}
    </div>
  )
}
