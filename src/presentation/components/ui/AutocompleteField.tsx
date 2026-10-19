import { useEffect, useId, useRef, useState } from 'react'
import { usePresence } from '../../hooks/use-presence'

interface AutocompleteOption {
  value: string
  label: string
  id?: string
}

interface AutocompleteFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  onSearch: (query: string) => Promise<AutocompleteOption[]>
  // Fired only when the user picks a suggestion (not on free-text typing) —
  // use this to capture fields like `option.id` that free text can't provide.
  onSelect?: (option: AutocompleteOption) => void
  placeholder?: string
  error?: string
  required?: boolean
  disabled?: boolean
  minQueryLength?: number
  debounceMs?: number
}

// Free-text input with a debounced, async-searched suggestion list — for
// fields backed by a server-side search endpoint rather than a fixed option
// set (so it can't reuse SelectField, which renders every option up front).
export function AutocompleteField({
  label,
  value,
  onChange,
  onSearch,
  onSelect,
  placeholder,
  error,
  required,
  disabled,
  minQueryLength = 2,
  debounceMs = 300,
}: AutocompleteFieldProps) {
  const inputId = useId()
  const [query, setQuery] = useState(value)
  const [options, setOptions] = useState<AutocompleteOption[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const requestId = useRef(0)
  // Fades out under the field before unmounting (ui-motion "Popovers and
  // menus animate from their anchor").
  const suggestions = usePresence(isOpen && query.trim().length >= minQueryLength)

  useEffect(() => {
    setQuery(value)
  }, [value])

  useEffect(() => {
    if (query.trim().length < minQueryLength) {
      setOptions([])
      setIsLoading(false)
      return
    }

    const currentRequestId = ++requestId.current
    setIsLoading(true)
    const timeoutId = setTimeout(() => {
      onSearch(query.trim())
        .then((results) => {
          if (requestId.current === currentRequestId) setOptions(results)
        })
        .catch(() => {
          if (requestId.current === currentRequestId) setOptions([])
        })
        .finally(() => {
          if (requestId.current === currentRequestId) setIsLoading(false)
        })
    }, debounceMs)

    return () => clearTimeout(timeoutId)
  }, [query, minQueryLength, debounceMs, onSearch])

  const handleSelect = (option: AutocompleteOption) => {
    setQuery(option.label)
    onChange(option.value)
    onSelect?.(option)
    setIsOpen(false)
  }

  const handleInputChange = (nextQuery: string) => {
    setQuery(nextQuery)
    onChange(nextQuery)
    setIsOpen(true)
  }

  return (
    <div className="relative flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-body font-medium text-text">
        {label}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>
      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={isOpen}
        aria-autocomplete="list"
        autoComplete="off"
        value={query}
        onChange={(event) => handleInputChange(event.target.value)}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setTimeout(() => setIsOpen(false), 150)}
        placeholder={placeholder}
        aria-required={required}
        disabled={disabled}
        className={`rounded-lg border bg-surface px-3 py-2 text-body text-text max-sm:text-base max-lg:min-h-10 placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent disabled:opacity-60 ${
          error ? 'border-danger' : 'border-border'
        }`}
      />
      {suggestions.isMounted && (
        <ul
          role="listbox"
          data-state={suggestions.state}
          onAnimationEnd={suggestions.onAnimationEnd}
          className={`motion-popover absolute top-full z-10 mt-1 max-h-60 w-full origin-top overflow-auto rounded-lg border border-border bg-surface py-1 shadow-lg ${
            suggestions.state === 'closing' ? 'pointer-events-none' : ''
          }`}
        >
          {isLoading && <li className="px-3 py-2 text-body text-text-muted">Searching…</li>}
          {!isLoading && options.length === 0 && <li className="px-3 py-2 text-body text-text-muted">No matches found</li>}
          {!isLoading &&
            options.map((option) => (
              <li
                key={option.value}
                role="option"
                aria-selected={option.value === value}
                onMouseDown={(event) => {
                  event.preventDefault()
                  handleSelect(option)
                }}
                className="cursor-pointer px-3 py-2 text-body text-text hover:bg-secondary-accent/10"
              >
                {option.label}
              </li>
            ))}
        </ul>
      )}
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
