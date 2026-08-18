import { useId } from 'react'

interface TextareaFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  rows?: number
  labelClassName?: string
}

export function TextareaField({ label, value, onChange, placeholder, rows = 4, labelClassName }: TextareaFieldProps) {
  const textareaId = useId()

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={textareaId} className={labelClassName ?? 'text-body font-medium text-text'}>
        {label}
      </label>
      <textarea
        id={textareaId}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="rounded-lg border border-border px-3 py-2 text-body text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-secondary-accent"
      />
    </div>
  )
}
