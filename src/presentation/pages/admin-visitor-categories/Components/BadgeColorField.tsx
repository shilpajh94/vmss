import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'

interface BadgeColorFieldProps {
  value: VisitorCategory['badgeColor']
  onChange: (value: VisitorCategory['badgeColor']) => void
  labelClassName?: string
}

const OPTIONS: Array<{ value: VisitorCategory['badgeColor']; label: string; swatchClassName: string }> = [
  { value: 'blue', label: 'Blue', swatchClassName: 'bg-info' },
  { value: 'orange', label: 'Orange', swatchClassName: 'bg-warning' },
  { value: 'gold', label: 'Gold', swatchClassName: 'bg-vip' },
  { value: 'grey', label: 'Grey', swatchClassName: 'bg-text-muted' },
]

export function BadgeColorField({ value, onChange, labelClassName }: BadgeColorFieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className={labelClassName ?? 'text-body font-medium text-text'}>Badge Color</span>
      <div className="flex items-center gap-3">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            aria-pressed={value === option.value}
            aria-label={option.label}
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 font-body text-sm text-text ${
              value === option.value ? 'border-admin-accent ring-2 ring-admin-accent/30' : 'border-border'
            }`}
          >
            <span className={`size-5 rounded border border-border ${option.swatchClassName}`} />
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}
