import { useId } from 'react'

interface SelectOption {
  value: string
  label: string
}

interface SelectFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  error?: string
  required?: boolean
  disabled?: boolean
  labelClassName?: string
  /** Set when the placeholder itself is a valid, reselectable choice (e.g. "All branches"), not just a prompt. */
  placeholderSelectable?: boolean
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  placeholder,
  error,
  required,
  disabled,
  labelClassName,
  placeholderSelectable,
}: SelectFieldProps) {
  const selectId = useId()
  const errorId = `${selectId}-error`

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={selectId} className={labelClassName ?? 'text-body font-medium text-text'}>
        {label}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>
      <select
        id={selectId}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        disabled={disabled}
        className={`rounded-lg border bg-surface px-3 py-2 text-body text-text max-sm:text-base max-lg:min-h-10 focus:outline-none focus:ring-2 focus:ring-secondary-accent disabled:opacity-60 ${
          error ? 'border-danger' : 'border-border'
        }`}
      >
        <option value="" disabled={!placeholderSelectable}>
          {placeholder ?? 'Select'}
        </option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && (
        <p id={errorId} className="text-caption text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
