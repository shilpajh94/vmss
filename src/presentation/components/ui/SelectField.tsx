import { useId } from 'react'
import { SelectDropdown } from './SelectDropdown'
import type { DropdownOption } from './SelectDropdown'

interface SelectFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  options: DropdownOption[]
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

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={selectId} className={labelClassName ?? 'text-body font-medium text-text'}>
        {label}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>
      <SelectDropdown
        id={selectId}
        ariaLabel={label}
        options={options}
        value={value}
        onChange={onChange}
        placeholder={placeholder ?? 'Select'}
        placeholderSelectable={placeholderSelectable}
        required={required}
        disabled={disabled}
        error={Boolean(error)}
      />
      {error && <p className="text-caption text-danger">{error}</p>}
    </div>
  )
}
