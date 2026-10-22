import { useId } from 'react'

interface TextareaFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  rows?: number
  labelClassName?: string
  disabled?: boolean
  error?: string
  required?: boolean
  // The API's column limit (see TextField).
  maxLength?: number
}

export function TextareaField({
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
  labelClassName,
  disabled,
  error,
  required,
  maxLength,
}: TextareaFieldProps) {
  const textareaId = useId()
  const errorId = `${textareaId}-error`

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={textareaId} className={labelClassName ?? 'text-body font-medium text-text'}>
        {label}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>
      <textarea
        id={textareaId}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        maxLength={maxLength}
        aria-required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`rounded-lg border px-3 py-2 text-body text-text max-sm:text-base placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent disabled:opacity-60 ${
          error ? 'border-danger' : 'border-border'
        }`}
      />
      {error && (
        <p id={errorId} className="text-caption text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
