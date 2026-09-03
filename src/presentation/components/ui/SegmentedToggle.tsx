interface SegmentedToggleOption {
  value: string
  label: string
}

interface SegmentedToggleProps {
  options: SegmentedToggleOption[]
  value: string
  onChange: (value: string) => void
  /**
   * 'inline' (default): auto-width buttons, no gap — used by most toggles.
   * 'pill': padded track with a floating rounded pill for the active option (e.g. Registration type).
   * 'divided': full-width equal segments separated by a hairline divider (e.g. Preferred Contact Method).
   */
  variant?: 'inline' | 'pill' | 'divided'
}

export function SegmentedToggle({ options, value, onChange, variant = 'inline' }: SegmentedToggleProps) {
  if (variant === 'pill') {
    return (
      <div className="flex h-11 w-full items-center rounded-lg border border-border bg-[#f8fafc] p-1">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`flex h-full flex-1 items-center justify-center rounded-md text-sm font-semibold transition-colors ${
              value === option.value ? 'bg-secondary-accent text-white' : 'text-text-muted hover:bg-secondary-accent/10 hover:text-text'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    )
  }

  if (variant === 'divided') {
    return (
      <div className="flex h-10 w-full overflow-hidden rounded-lg border border-border bg-surface">
        {options.map((option, index) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`flex h-full flex-1 items-center justify-center text-[13px] font-semibold ${index > 0 ? 'border-l border-border' : ''} ${
              value === option.value ? 'bg-secondary-accent text-white' : 'bg-surface text-text'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="inline-flex overflow-hidden rounded-lg border border-border">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`px-4 py-2 text-body font-medium ${
            value === option.value ? 'bg-secondary-accent text-white' : 'bg-surface text-text'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
