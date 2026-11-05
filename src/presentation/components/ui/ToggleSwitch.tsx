import { useId } from 'react'

interface ToggleSwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  disabled?: boolean
}

interface SwitchControlProps {
  id: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
  labelledBy?: string
}

// The visual switch alone, shared by the inline `ToggleSwitch` row and the
// form-field `SwitchField` layout.
function SwitchControl({ id, checked, onChange, labelledBy, disabled }: SwitchControlProps) {
  return (
    <span className="relative inline-flex shrink-0">
      <input
        id={id}
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        aria-labelledby={labelledBy}
        onChange={(event) => onChange(event.target.checked)}
        className="peer sr-only"
      />
      {/* The input is visually hidden, so the track carries its focus ring. */}
      <span
        className={`h-6 w-11 rounded-full transition-colors duration-standard peer-focus-visible:ring-2 peer-focus-visible:ring-secondary-accent peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-surface ${
          checked ? 'bg-admin-accent' : 'bg-neutral-subtle'
        }`}
      />
      <span
        className={`absolute top-0.5 left-0.5 size-5 rounded-full bg-knob shadow transition-transform duration-standard ease-motion-out ${
          checked ? 'translate-x-5' : ''
        }`}
      />
    </span>
  )
}

export function ToggleSwitch({ checked, onChange, label, disabled }: ToggleSwitchProps) {
  const switchId = useId()

  return (
    <label htmlFor={switchId} className={`flex w-full items-center justify-between gap-3 ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}>
      <span className={`text-body font-semibold ${checked ? 'text-admin-accent' : 'text-text-faint'}`}>{label}</span>
      <SwitchControl id={switchId} checked={checked} onChange={onChange} disabled={disabled} />
    </label>
  )
}

interface SwitchFieldProps {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
  // Text beside the switch describing the current state, e.g. "Active / Open".
  stateLabel: string
}

// A switch laid out like the other form fields: the label on top, then the
// switch and its state text on one row, so it top-aligns with a neighbouring
// input or textarea (responsive-layout "Form Toggle Fields Align With
// Neighbouring Fields").
export function SwitchField({ label, checked, onChange, stateLabel }: SwitchFieldProps) {
  const switchId = useId()
  const labelId = `${switchId}-label`

  return (
    <div className="flex flex-col gap-1.5">
      <span id={labelId} className="text-body font-medium text-text">
        {label}
      </span>
      <label htmlFor={switchId} className="flex min-h-10 cursor-pointer items-center gap-3">
        <SwitchControl id={switchId} checked={checked} onChange={onChange} labelledBy={labelId} />
        <span className="font-body text-sm font-semibold text-text">{stateLabel}</span>
      </label>
    </div>
  )
}
