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
  // Names the select that stands in for the segments on a phone.
  ariaLabel?: string
}

// More segments than this don't fit side by side on a phone.
const MAX_PHONE_SEGMENTS = 3

export function SegmentedToggle(props: SegmentedToggleProps) {
  if (props.options.length <= MAX_PHONE_SEGMENTS) return <Segments {...props} />
  // Past three options: a select below `sm`, the segments from `sm` up.
  return (
    <>
      <select
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        aria-label={props.ariaLabel}
        className="min-h-10 w-full rounded-lg border border-border bg-surface px-3 py-2 text-base text-text focus:outline-none focus:ring-2 focus:ring-secondary-accent sm:hidden"
      >
        {props.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <div className="hidden sm:contents">
        <Segments {...props} />
      </div>
    </>
  )
}

function Segments({ options, value, onChange, variant = 'inline' }: SegmentedToggleProps) {
  if (variant === 'pill') {
    const activeIndex = options.findIndex((option) => option.value === value)
    return (
      <div className="relative flex h-11 w-full items-center rounded-lg border border-border bg-surface-muted p-1">
        {/* One pill that glides to the selected segment (ui-motion "Toggling a
            switch"), instead of each button snapping its own background. */}
        {activeIndex >= 0 && (
          <span
            aria-hidden
            className="absolute inset-y-1 left-1 rounded-md bg-secondary-accent transition-transform duration-standard ease-motion-out"
            style={{ width: `calc((100% - 0.5rem) / ${options.length})`, transform: `translateX(${activeIndex * 100}%)` }}
          />
        )}
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`relative flex h-full flex-1 cursor-pointer items-center justify-center rounded-md text-sm font-semibold transition-colors duration-standard ${
              value === option.value ? 'text-on-accent' : 'text-text-muted hover:bg-secondary-accent/10 hover:text-text'
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
            className={`flex h-full flex-1 cursor-pointer items-center justify-center text-[13px] font-semibold transition-colors duration-standard ${index > 0 ? 'border-l border-border' : ''} ${
              value === option.value ? 'bg-secondary-accent text-on-accent' : 'bg-surface text-text hover:bg-secondary-accent/10'
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
          className={`cursor-pointer px-4 py-2 text-body font-medium max-lg:min-h-10 transition-colors duration-standard ${
            value === option.value ? 'bg-secondary-accent text-on-accent' : 'bg-surface text-text hover:bg-secondary-accent/10'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
