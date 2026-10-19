import type { ComponentType, SVGProps } from 'react'
import { ChevronDownIcon } from '../icons'

export interface DropdownOption {
  value: string
  label: string
}

interface DropdownFilterProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  value: string
  options: DropdownOption[]
  onChange: (value: string) => void
  ariaLabel: string
}

export function DropdownFilter({ icon: Icon, value, options, onChange, ariaLabel }: DropdownFilterProps) {
  return (
    <div className="relative flex h-10 w-full shrink-0 items-center sm:w-[200px] gap-2 rounded-lg border border-[#cbd5e1] bg-surface px-3">
      <Icon className="size-4 shrink-0 text-text" />
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={ariaLabel}
        className="min-w-0 flex-1 appearance-none bg-transparent font-body text-[13px] font-semibold text-text max-sm:text-base focus:outline-none"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDownIcon className="pointer-events-none size-4 shrink-0 text-text" />
    </div>
  )
}
