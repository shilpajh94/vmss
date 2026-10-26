import type { ComponentType, SVGProps } from 'react'
import { useDropdownPanel } from '../../hooks/use-dropdown-panel'
import { CheckIcon, ChevronDownIcon } from '../icons'
import type { DropdownOption } from './DropdownFilter'

interface MultiSelectFilterProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  options: DropdownOption[]
  /** Selected option values; empty means "no filter". */
  values: string[]
  onChange: (values: string[]) => void
  /** Trigger text when nothing is selected, e.g. "All statuses". */
  allLabel: string
  ariaLabel: string
}

export function summarizeSelection(options: DropdownOption[], values: string[], allLabel: string): string {
  const labels = options.filter((option) => values.includes(option.value)).map((option) => option.label)
  if (labels.length === 0) return allLabel
  return labels.length === 1 ? labels[0] : `${labels[0]} +${labels.length - 1}`
}

// Ticking every option is the same as filtering nothing, so it collapses to
// the empty selection (and the trigger reads the "All …" label again).
function normalise(options: DropdownOption[], values: string[]): string[] {
  return values.length >= options.length ? [] : values
}

// Themed replacement for the native <select> on the board filter bar, holding
// several values at once.
export function MultiSelectFilter({ icon: Icon, options, values, onChange, allLabel, ariaLabel }: MultiSelectFilterProps) {
  const toggle = (value: string) => {
    const next = values.includes(value) ? values.filter((current) => current !== value) : [...values, value]
    onChange(normalise(options, next))
  }

  const {
    isOpen,
    open,
    close,
    activeIndex,
    setActiveIndex,
    rootRef,
    triggerRef,
    listRef,
    listId,
    handleTriggerKeyDown,
    handleListKeyDown,
  } = useDropdownPanel({
    count: options.length,
    getInitialIndex: () => options.findIndex((option) => values.includes(option.value)),
    onSelect: (index) => toggle(options[index].value),
    getLabel: (index) => options[index].label,
  })

  const hasSelection = values.length > 0

  return (
    <div ref={rootRef} className="relative w-full shrink-0 sm:w-[200px]">
      <button
        ref={triggerRef}
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listId : undefined}
        onClick={() => (isOpen ? close() : open())}
        onKeyDown={handleTriggerKeyDown}
        className={`flex h-10 w-full items-center gap-2 rounded-lg border bg-surface px-3 transition-colors hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-secondary-accent focus-visible:outline-none ${
          hasSelection ? 'border-admin-accent' : 'border-border-strong'
        }`}
      >
        <Icon className={`size-4 shrink-0 ${hasSelection ? 'text-admin-accent' : 'text-text'}`} />
        <span className="min-w-0 flex-1 truncate text-left font-body text-[13px] font-semibold text-text max-sm:text-base">
          {summarizeSelection(options, values, allLabel)}
        </span>
        <ChevronDownIcon className={`size-4 shrink-0 text-text transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen ? (
        <div className="absolute left-0 z-30 mt-1.5 w-full min-w-[220px] overflow-hidden rounded-xl border border-border bg-surface shadow-lg max-sm:min-w-0">
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            aria-multiselectable="true"
            aria-label={ariaLabel}
            aria-activedescendant={`${listId}-${activeIndex}`}
            tabIndex={0}
            onKeyDown={handleListKeyDown}
            className="max-h-64 overflow-y-auto p-1 focus:outline-none"
          >
            {options.map((option, index) => {
              const selected = values.includes(option.value)
              return (
                <li
                  key={option.value}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={selected}
                  onClick={() => toggle(option.value)}
                  onMouseEnter={() => setActiveIndex(index)}
                  className={`flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 font-body text-[13px] text-text max-sm:py-2.5 max-sm:text-base ${
                    index === activeIndex ? 'bg-surface-muted' : ''
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`flex size-4 shrink-0 items-center justify-center rounded border ${
                      selected ? 'border-admin-accent bg-admin-accent text-on-accent' : 'border-border-strong bg-surface'
                    }`}
                  >
                    {selected ? <CheckIcon className="size-3" /> : null}
                  </span>
                  <span className={`min-w-0 flex-1 truncate ${selected ? 'font-semibold' : ''}`}>{option.label}</span>
                </li>
              )
            })}
          </ul>
          <div className="flex items-center justify-between border-t border-border px-3 py-2">
            <span className="font-body text-xs text-text-muted">{hasSelection ? `${values.length} selected` : allLabel}</span>
            <button
              type="button"
              disabled={!hasSelection}
              onClick={() => onChange([])}
              className="font-body text-[13px] font-semibold text-admin-accent disabled:text-text-faint"
            >
              Clear
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
