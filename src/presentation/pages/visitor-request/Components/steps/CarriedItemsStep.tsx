import { Checkbox } from '../../../../components/ui/Checkbox'
import { TextareaField } from '../../../../components/ui/TextareaField'
import type { CarriedItemsFormState } from '../../types'

const ITEM_CATEGORIES = [
  { value: 'laptop-tablet', label: 'Laptop / Tablet' },
  { value: 'mobile-phone', label: 'Mobile Phone' },
  { value: 'camera-recording-device', label: 'Camera / Recording Device' },
  { value: 'usb-external-storage', label: 'USB Drive / External Storage' },
  { value: 'tools-equipment', label: 'Tools / Equipment' },
  { value: 'food-beverages', label: 'Food / Beverages' },
  { value: 'other', label: 'Other' },
]

interface CarriedItemsStepProps {
  value: CarriedItemsFormState
  onChange: (value: CarriedItemsFormState) => void
}

export function CarriedItemsStep({ value, onChange }: CarriedItemsStepProps) {
  const toggleCategory = (category: string, checked: boolean) => {
    onChange({
      ...value,
      categories: checked ? [...value.categories, category] : value.categories.filter((item) => item !== category),
    })
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-h3 text-text">Carried Items</h3>
        <p className="text-body text-text-muted">Please declare any items you will be carrying into the premises for security clearance.</p>
      </div>
      <div className="flex flex-col gap-2">
        {ITEM_CATEGORIES.map((category) => (
          <div key={category.value} className="rounded-lg border border-border px-4 py-3">
            <Checkbox checked={value.categories.includes(category.value)} onChange={(checked) => toggleCategory(category.value, checked)}>
              {category.label}
            </Checkbox>
          </div>
        ))}
      </div>
      <TextareaField
        label="Item Description / Serial Numbers (Optional)"
        placeholder="Provide details about items, brand, model, or serial numbers…"
        value={value.description}
        onChange={(description) => onChange({ ...value, description })}
      />
    </div>
  )
}
