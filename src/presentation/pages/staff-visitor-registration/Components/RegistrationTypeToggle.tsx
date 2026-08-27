import { SegmentedToggle } from '../../../components/ui/SegmentedToggle'
import type { RegistrationType } from '../../visitor-request/types'

interface RegistrationTypeToggleProps {
  value: RegistrationType
  onChange: (value: RegistrationType) => void
}

export function RegistrationTypeToggle({ value, onChange }: RegistrationTypeToggleProps) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-6">
      <h3 className="font-display text-base font-semibold text-text">Registration type</h3>
      <div className="w-[320px]">
        <SegmentedToggle
          options={[
            { value: 'individual', label: 'Individual' },
            { value: 'group', label: 'Group' },
          ]}
          value={value}
          onChange={(next) => onChange(next as RegistrationType)}
          variant="pill"
        />
      </div>
    </div>
  )
}
