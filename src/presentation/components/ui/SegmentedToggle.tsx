interface SegmentedToggleOption {
  value: string
  label: string
}

interface SegmentedToggleProps {
  options: SegmentedToggleOption[]
  value: string
  onChange: (value: string) => void
}

export function SegmentedToggle({ options, value, onChange }: SegmentedToggleProps) {
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
