import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentType,
  type KeyboardEvent,
  type SVGProps,
} from 'react'
import { createPortal } from 'react-dom'
import { usePresence } from '../../hooks/use-presence'
import { CheckIcon, ChevronDownIcon } from '../icons'
import {
  TYPEAHEAD_RESET_MS,
  firstEnabled,
  initialActiveIndex,
  lastEnabled,
  nextEnabledIndex,
  typeaheadMatch,
} from './select-navigation'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  /** Muted trigger text while `value` matches no option. */
  placeholder?: string
  /** Pair with a `<label htmlFor>`; a button is labelable, so that names the combobox. */
  id?: string
  ariaLabel?: string
  ariaDescribedBy?: string
  required?: boolean
  invalid?: boolean
  disabled?: boolean
  icon?: ComponentType<SVGProps<SVGSVGElement>>
  size?: 'md' | 'sm'
  tone?: 'default' | 'admin'
  /** Extra trigger classes (width, min-height overrides). */
  className?: string
}

interface PanelPosition {
  left: number
  top?: number
  bottom?: number
  minWidth: number
  maxWidth: number
  maxHeight: number
  placement: 'bottom' | 'top'
}

const PANEL_GAP = 4
const VIEWPORT_MARGIN = 8
const PANEL_MAX_HEIGHT = 280
// Below this much room under the trigger, open upward if there's more above.
const MIN_SPACE_BELOW = 200

const TONE = {
  default: {
    ring: 'focus-visible:ring-secondary-accent',
    open: 'border-secondary-accent ring-2 ring-secondary-accent/25',
    active: 'bg-secondary-accent/10',
    check: 'text-secondary-accent',
  },
  admin: {
    ring: 'focus-visible:ring-admin-accent',
    open: 'border-admin-accent ring-2 ring-admin-accent/25',
    active: 'bg-admin-accent/10',
    check: 'text-admin-accent',
  },
} as const

function measure(trigger: HTMLElement): PanelPosition | undefined {
  const rect = trigger.getBoundingClientRect()
  // Scrolled out of view: the panel would float detached from nothing.
  if (rect.bottom < 0 || rect.top > window.innerHeight) return undefined
  const spaceBelow = window.innerHeight - rect.bottom - PANEL_GAP - VIEWPORT_MARGIN
  const spaceAbove = rect.top - PANEL_GAP - VIEWPORT_MARGIN
  const placement = spaceBelow < MIN_SPACE_BELOW && spaceAbove > spaceBelow ? 'top' : 'bottom'
  const left = Math.max(VIEWPORT_MARGIN, rect.left)
  return {
    left,
    top: placement === 'bottom' ? rect.bottom + PANEL_GAP : undefined,
    bottom: placement === 'top' ? window.innerHeight - rect.top + PANEL_GAP : undefined,
    minWidth: rect.width,
    maxWidth: Math.max(rect.width, window.innerWidth - left - VIEWPORT_MARGIN),
    maxHeight: Math.min(PANEL_MAX_HEIGHT, placement === 'bottom' ? spaceBelow : spaceAbove),
    placement,
  }
}

// The app's one single-choice dropdown (select-dropdowns spec): a
// select-only combobox. Focus never leaves the trigger; the active option is
// conveyed with aria-activedescendant (design.md D2). The listbox is portalled
// with fixed positioning so modals and scrolling cards can't clip it (D4).
export function Select({
  value,
  onChange,
  options,
  placeholder = 'Select',
  id,
  ariaLabel,
  ariaDescribedBy,
  required,
  invalid,
  disabled,
  icon: Icon,
  size = 'md',
  tone = 'default',
  className = '',
}: SelectProps) {
  const listboxId = useId()
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listboxRef = useRef<HTMLUListElement>(null)
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [position, setPosition] = useState<PanelPosition | undefined>(undefined)
  const typeahead = useRef({ buffer: '', timeoutId: 0 })
  const panel = usePresence(isOpen)
  const toneClasses = TONE[tone]

  const selected = options.find((option) => option.value === value)
  const optionId = (index: number) => `${listboxId}-option-${index}`

  const open = useCallback(
    (startIndex?: number) => {
      if (disabled || !triggerRef.current) return
      const measured = measure(triggerRef.current)
      if (!measured) return
      setPosition(measured)
      setActiveIndex(startIndex ?? initialActiveIndex(options, value))
      setIsOpen(true)
    },
    [disabled, options, value],
  )

  const close = useCallback(() => setIsOpen(false), [])

  const choose = (index: number) => {
    const option = options[index]
    if (!option || option.disabled) return
    setIsOpen(false)
    triggerRef.current?.focus()
    if (option.value !== value) onChange(option.value)
  }

  // Follow the trigger while the page scrolls or resizes; close once it
  // leaves the viewport. Scrolling inside the listbox itself is ignored.
  useEffect(() => {
    if (!isOpen) return
    const reposition = (event: Event) => {
      if (event.target instanceof Node && listboxRef.current?.contains(event.target)) return
      const measured = triggerRef.current ? measure(triggerRef.current) : undefined
      if (measured) setPosition(measured)
      else setIsOpen(false)
    }
    const closeOnOutsidePointer = (event: PointerEvent) => {
      const target = event.target as Node
      if (triggerRef.current?.contains(target) || listboxRef.current?.contains(target)) return
      setIsOpen(false)
    }
    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, true)
    document.addEventListener('pointerdown', closeOnOutsidePointer)
    return () => {
      window.removeEventListener('resize', reposition)
      window.removeEventListener('scroll', reposition, true)
      document.removeEventListener('pointerdown', closeOnOutsidePointer)
    }
  }, [isOpen])

  // Keep the active option in view without scrolling anything outside the listbox.
  useLayoutEffect(() => {
    const listbox = listboxRef.current
    if (!isOpen || !listbox || activeIndex < 0) return
    const element = listbox.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`)
    if (!element) return
    if (element.offsetTop < listbox.scrollTop) listbox.scrollTop = element.offsetTop - 4
    else if (element.offsetTop + element.offsetHeight > listbox.scrollTop + listbox.clientHeight) {
      listbox.scrollTop = element.offsetTop + element.offsetHeight - listbox.clientHeight + 4
    }
  }, [isOpen, activeIndex, panel.isMounted])

  useEffect(() => () => window.clearTimeout(typeahead.current.timeoutId), [])

  const runTypeahead = (char: string) => {
    const state = typeahead.current
    window.clearTimeout(state.timeoutId)
    state.buffer += char
    state.timeoutId = window.setTimeout(() => {
      state.buffer = ''
    }, TYPEAHEAD_RESET_MS)
    const from = isOpen ? activeIndex : initialActiveIndex(options, value)
    const match = typeaheadMatch(options, state.buffer, from)
    if (match < 0) return
    if (isOpen) setActiveIndex(match)
    else open(match)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const { key } = event
    if (!isOpen) {
      if (['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(key)) {
        event.preventDefault()
        open()
      } else if (key === 'Home' || key === 'End') {
        event.preventDefault()
        open(key === 'Home' ? firstEnabled(options) : lastEnabled(options))
      } else if (key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        runTypeahead(key)
      }
      return
    }
    switch (key) {
      case 'ArrowDown':
      case 'ArrowUp':
        event.preventDefault()
        setActiveIndex((current) => nextEnabledIndex(options, current, key === 'ArrowDown' ? 1 : -1))
        return
      case 'Home':
      case 'End':
        event.preventDefault()
        setActiveIndex(key === 'Home' ? firstEnabled(options) : lastEnabled(options))
        return
      case 'Enter':
        event.preventDefault()
        choose(activeIndex)
        return
      case ' ':
        event.preventDefault()
        // Mid type-ahead, a space is part of the label being typed ("West Wing").
        if (typeahead.current.buffer) runTypeahead(' ')
        else choose(activeIndex)
        return
      case 'Escape':
        event.preventDefault()
        // Stop here so an enclosing modal's focus trap doesn't also close the modal.
        event.stopPropagation()
        close()
        return
      case 'Tab':
        close()
        return
      default:
        if (key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) runTypeahead(key)
    }
  }

  const sizeClasses =
    size === 'sm'
      ? 'h-10 px-3 text-[13px] font-semibold'
      : 'px-3 py-2 text-body max-lg:min-h-10'
  const borderClasses = invalid ? 'border-danger' : size === 'sm' ? 'border-border-strong' : 'border-border'

  return (
    <>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        aria-activedescendant={isOpen && activeIndex >= 0 ? optionId(activeIndex) : undefined}
        aria-label={ariaLabel}
        aria-describedby={ariaDescribedBy}
        aria-required={required || undefined}
        aria-invalid={invalid || undefined}
        disabled={disabled}
        onClick={() => (isOpen ? close() : open())}
        onKeyDown={onKeyDown}
        onBlur={close}
        className={`group flex w-full min-w-0 items-center gap-2 rounded-lg border bg-surface text-left font-body text-text transition-[border-color,box-shadow] duration-fast hover:border-border-strong focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:border-border max-sm:text-base ${sizeClasses} ${borderClasses} ${toneClasses.ring} ${
          isOpen && !invalid ? toneClasses.open : ''
        } ${className}`}
      >
        {Icon ? <Icon className="size-4 shrink-0 text-text" /> : null}
        <span className={`min-w-0 flex-1 truncate ${selected ? '' : 'font-normal text-text-muted'}`}>
          {selected ? selected.label : placeholder}
        </span>
        <ChevronDownIcon
          className={`size-4 shrink-0 text-text-muted transition-transform duration-standard ease-motion-out group-hover:text-text motion-reduce:transition-none ${
            isOpen ? 'rotate-180 text-text' : ''
          }`}
        />
      </button>
      {panel.isMounted && position
        ? createPortal(
            <ul
              ref={listboxRef}
              id={listboxId}
              role="listbox"
              tabIndex={-1}
              data-select-panel=""
              data-state={panel.state}
              onAnimationEnd={panel.onAnimationEnd}
              // Keep focus (and so aria-activedescendant) on the trigger.
              onMouseDown={(event) => event.preventDefault()}
              style={{
                left: position.left,
                top: position.top,
                bottom: position.bottom,
                minWidth: position.minWidth,
                maxWidth: position.maxWidth,
                maxHeight: position.maxHeight,
              }}
              className={`motion-popover scrollbar-thin fixed z-[70] flex flex-col gap-0.5 overflow-y-auto overscroll-contain rounded-xl border border-border bg-surface p-1 font-body shadow-[0_12px_32px_rgba(15,23,42,0.16)] ${
                position.placement === 'bottom' ? 'origin-top' : 'origin-bottom'
              }`}
            >
              {options.length === 0 ? (
                <li role="presentation" className="px-2.5 py-2 text-sm text-text-muted">
                  No options available
                </li>
              ) : (
                options.map((option, index) => {
                  const isSelected = option.value === value
                  const isActive = index === activeIndex
                  return (
                    <li
                      key={`${option.value}-${index}`}
                      id={optionId(index)}
                      data-index={index}
                      role="option"
                      aria-selected={isSelected}
                      aria-disabled={option.disabled || undefined}
                      onPointerMove={() => {
                        if (!option.disabled && activeIndex !== index) setActiveIndex(index)
                      }}
                      onClick={() => choose(index)}
                      className={`flex cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-text transition-colors duration-fast select-none max-sm:min-h-11 max-sm:text-base ${
                        isActive && !option.disabled ? toneClasses.active : ''
                      } ${isSelected ? 'font-semibold' : 'font-medium'} ${
                        option.disabled ? 'cursor-not-allowed opacity-50' : ''
                      }`}
                    >
                      <span className="min-w-0 flex-1 truncate">{option.label}</span>
                      {isSelected ? <CheckIcon className={`size-4 shrink-0 ${toneClasses.check}`} /> : null}
                    </li>
                  )
                })
              )}
            </ul>,
            document.body,
          )
        : null}
    </>
  )
}
