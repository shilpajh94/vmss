import { SelectField } from '../../../components/ui/SelectField'
import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import type { OrganisationConfig } from '../../../../domain/entities/organisation-config-schema'

const BADGE_EXPIRY_OPTIONS = [
  { value: '4h', label: '4 Hours' },
  { value: '8h', label: '8 Hours (Standard Business Day)' },
  { value: '12h', label: '12 Hours' },
  { value: '24h', label: '24 Hours' },
]

interface VisitorPolicyCardProps {
  form: OrganisationConfig
  onAutoApproveChange: (autoApprovePreRegistered: boolean) => void
  onBadgeExpiryChange: (passBadgeExpiryDuration: string) => void
}

export function VisitorPolicyCard({ form, onAutoApproveChange, onBadgeExpiryChange }: VisitorPolicyCardProps) {
  return (
    <section className="flex flex-1 flex-col gap-5 rounded-2xl border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-bold text-text">Visitor Policy &amp; Security</h2>

      <ToggleSwitch
        label="Auto-approve pre-registered visitors"
        checked={form.autoApprovePreRegistered}
        onChange={onAutoApproveChange}
      />

      <SelectField
        label="Pass Badge Expiry Duration"
        value={form.passBadgeExpiryDuration}
        onChange={onBadgeExpiryChange}
        options={BADGE_EXPIRY_OPTIONS}
      />
    </section>
  )
}
