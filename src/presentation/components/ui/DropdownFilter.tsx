import type { ComponentType, SVGProps } from 'react'
import { SelectDropdown } from './SelectDropdown'

export type { DropdownOption } from './SelectDropdown'
import type { DropdownOption } from './SelectDropdown'

interface DropdownFilterProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  value: string
  options: DropdownOption[]
  onChange: (value: string) => void
  ariaLabel: string
}

export function DropdownFilter({ icon, value, options, onChange, ariaLabel }: DropdownFilterProps) {
  return <SelectDropdown variant="filter" icon={icon} value={value} options={options} onChange={onChange} ariaLabel={ariaLabel} />
}
