import { SegmentedToggle } from '../ui/SegmentedToggle'

export type InvitationView = 'board' | 'list'

const OPTIONS = [
  { value: 'board', label: 'Board' },
  { value: 'list', label: 'List' },
]

export function parseInvitationView(raw: unknown): InvitationView | undefined {
  return raw === 'board' || raw === 'list' ? raw : undefined
}

export function InvitationViewToggle({ value, onChange }: { value: InvitationView; onChange: (view: InvitationView) => void }) {
  return (
    <SegmentedToggle
      ariaLabel="Invitations view"
      options={OPTIONS}
      value={value}
      onChange={(next) => {
        const view = parseInvitationView(next)
        if (view) onChange(view)
      }}
    />
  )
}
