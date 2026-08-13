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
}

export function SelectField({ label, value, onChange, options, placeholder, error, required }: SelectFieldProps) {
  const selectId = useId()

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={selectId} className="text-body font-medium text-text">
        {label}
      </label>
      <select
        id={selectId}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-required={required}
        className={`rounded-lg border bg-surface px-3 py-2 text-body text-text focus:outline-none focus:ring-2 focus:ring-secondary-accent ${
          error ? 'border-danger' : 'border-border'
        }`}
      >
        <option value="" disabled>
          {placeholder ?? 'Select'}
        </option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
