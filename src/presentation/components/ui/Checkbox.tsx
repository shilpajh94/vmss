import type { ReactNode } from 'react'

interface CheckboxProps {
  checked: boolean
  onChange: (checked: boolean) => void
  children: ReactNode
  /** Visually hides `children` (via `sr-only`) while it stays inside this
   * `<label>`, so it remains the checkbox's accessible name. */
  hideLabel?: boolean
}

export function Checkbox({ checked, onChange, children, hideLabel }: CheckboxProps) {
  return (
    <label className="flex items-start gap-2 text-body text-text max-lg:gap-3 max-lg:py-1">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 size-4 shrink-0 rounded max-lg:size-5 border-border text-primary focus:outline-none focus:ring-2 focus:ring-secondary-accent"
      />
      <span className={hideLabel ? 'sr-only' : undefined}>{children}</span>
    </label>
  )
}
