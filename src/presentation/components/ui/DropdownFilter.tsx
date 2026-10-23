import type { ComponentType, SVGProps } from 'react'
import { Select } from './Select'

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

// The icon and chevron sit inside Select's trigger button, so clicking either
// opens the list (select-dropdowns "The whole trigger opens the dropdown").
export function DropdownFilter({ icon, value, options, onChange, ariaLabel }: DropdownFilterProps) {
  return (
    <div className="w-full shrink-0 sm:w-[200px]">
      <Select icon={icon} size="sm" value={value} options={options} onChange={onChange} ariaLabel={ariaLabel} />
    </div>
  )
}
