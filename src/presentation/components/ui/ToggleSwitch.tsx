import { useId } from 'react'

interface ToggleSwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
}

export function ToggleSwitch({ checked, onChange, label }: ToggleSwitchProps) {
  const switchId = useId()

  return (
    <label htmlFor={switchId} className="flex w-full cursor-pointer items-center justify-between gap-3">
      <span className={`text-body font-semibold ${checked ? 'text-admin-accent' : 'text-text-faint'}`}>{label}</span>
      <span className="relative inline-flex">
        <input
          id={switchId}
          type="checkbox"
          role="switch"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          className="peer sr-only"
        />
        <span
          className={`h-6 w-11 rounded-full transition-colors ${checked ? 'bg-admin-accent' : 'bg-neutral-subtle'}`}
        />
        <span
          className={`absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow transition-transform ${
            checked ? 'translate-x-5' : ''
          }`}
        />
      </span>
    </label>
  )
}
