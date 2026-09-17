import { useId } from 'react'

interface TextFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
  error?: string
  required?: boolean
  disabled?: boolean
  labelClassName?: string
  min?: string
  max?: string
}

export function TextField({ label, value, onChange, placeholder, type = 'text', error, required, disabled, labelClassName, min, max }: TextFieldProps) {
  const inputId = useId()

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className={labelClassName ?? 'text-body font-medium text-text'}>
        {label}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>
      <input
        id={inputId}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onClick={(event) => {
          // Firefox (and some Chromium builds) only open the native date/time
          // picker when the click lands exactly on the tiny calendar icon.
          // Forcing showPicker() on any click makes the whole field clickable.
          if (type === 'date' || type === 'time') {
            try {
              event.currentTarget.showPicker?.()
            } catch {
              // unsupported or blocked (e.g. no user-gesture context) — ignore
            }
          }
        }}
        placeholder={placeholder}
        aria-required={required}
        disabled={disabled}
        min={min}
        max={max}
        className={`rounded-lg border px-3 py-2 text-body text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent disabled:opacity-60 ${
          error ? 'border-danger' : 'border-border'
        }`}
      />
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
