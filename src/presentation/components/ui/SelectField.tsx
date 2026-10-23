import { useId } from 'react'
import { Select } from './Select'

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
  const prompt = placeholder ?? 'Select'

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={selectId} className={labelClassName ?? 'text-body font-medium text-text'}>
        {label}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>
      <Select
        id={selectId}
        value={value}
        onChange={onChange}
        options={placeholderSelectable ? [{ value: '', label: prompt }, ...options] : options}
        placeholder={prompt}
        required={required}
        invalid={Boolean(error)}
        ariaDescribedBy={error ? errorId : undefined}
        disabled={disabled}
      />
      {error && (
        <p id={errorId} className="text-caption text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
