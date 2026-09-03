import { useEffect, useId, useRef, useState } from 'react'

interface AutocompleteOption {
  value: string
  label: string
}

interface AutocompleteFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  onSearch: (query: string) => Promise<AutocompleteOption[]>
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
        className={`rounded-lg border bg-surface px-3 py-2 text-body text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent disabled:opacity-60 ${
          error ? 'border-danger' : 'border-border'
        }`}
      />
      {isOpen && query.trim().length >= minQueryLength && (
        <ul
          role="listbox"
          className="absolute top-full z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-border bg-surface py-1 shadow-lg"
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
