import { ToggleSwitch } from '../../../components/ui/ToggleSwitch'
import type { OrganisationConfig } from '../../../../domain/entities/organisation-config-schema'

interface VisitorPolicyCardProps {
  form: OrganisationConfig
  onAutoApproveChange: (autoApprovePreRegistered: boolean) => void
}

export function VisitorPolicyCard({ form, onAutoApproveChange }: VisitorPolicyCardProps) {
  return (
    <section className="flex flex-1 flex-col gap-5 rounded-2xl border border-border bg-surface p-6">
      <h2 className="font-display text-lg font-bold text-text">Visitor Policy &amp; Security</h2>

      <ToggleSwitch
        label="Auto-approve pre-registered visitors"
        checked={form.autoApprovePreRegistered}
        onChange={onAutoApproveChange}
      />
    </section>
  )
}
