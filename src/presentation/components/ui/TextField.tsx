import { useId } from 'react'

interface TextFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
  error?: string
  required?: boolean
  labelClassName?: string
}

export function TextField({ label, value, onChange, placeholder, type = 'text', error, required, labelClassName }: TextFieldProps) {
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
        placeholder={placeholder}
        aria-required={required}
        className={`rounded-lg border px-3 py-2 text-body text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent ${
          error ? 'border-danger' : 'border-border'
        }`}
      />
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
