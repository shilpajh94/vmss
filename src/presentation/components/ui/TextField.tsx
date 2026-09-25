import { useId } from 'react'

interface TextFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  onBlur?: () => void
  placeholder?: string
  type?: string
  error?: string
  required?: boolean
  disabled?: boolean
  // Distinct from `disabled`: the value stays legible and still submits as
  // part of the form, it just can't be edited (e.g. a name locked because
  // the server will silently discard any edit to it).
  readOnly?: boolean
  helperText?: string
  labelClassName?: string
  min?: string
  max?: string
}

export function TextField({
  label,
  value,
  onChange,
  onBlur,
  placeholder,
  type = 'text',
  error,
  required,
  disabled,
  readOnly,
  helperText,
  labelClassName,
  min,
  max,
}: TextFieldProps) {
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
        onBlur={onBlur}
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
        readOnly={readOnly}
        min={min}
        max={max}
        className={`rounded-lg border px-3 py-2 text-body text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent disabled:opacity-60 ${
          readOnly ? 'cursor-default bg-border-subtle text-text-muted' : ''
        } ${error ? 'border-danger' : 'border-border'}`}
      />
      {helperText && !error && <p className="text-caption text-text-muted">{helperText}</p>}
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
