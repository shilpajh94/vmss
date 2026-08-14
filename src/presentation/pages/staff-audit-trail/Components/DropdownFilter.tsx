import type { ComponentType, SVGProps } from 'react'
import { ChevronDownIcon } from '../../../components/icons'
import type { DropdownOption } from '../types'

interface DropdownFilterProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  value: string
  options: DropdownOption[]
  onChange: (value: string) => void
  ariaLabel: string
}

export function DropdownFilter({ icon: Icon, value, options, onChange, ariaLabel }: DropdownFilterProps) {
  return (
    <div className="relative flex h-10 w-[220px] shrink-0 items-center gap-2 rounded-lg border border-[#cbd5e1] bg-surface px-3">
      <Icon className="size-4 shrink-0 text-text" />
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={ariaLabel}
        className="flex-1 appearance-none bg-transparent font-body text-[13px] font-semibold text-text focus:outline-none"
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
