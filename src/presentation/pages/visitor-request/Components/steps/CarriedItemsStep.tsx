import { Checkbox } from '../../../../components/ui/Checkbox'
import { TextareaField } from '../../../../components/ui/TextareaField'
import type { CarriedItemsFormState } from '../../types'

// Values must match the backend's `carriedItems.items` enum for
// POST /registrations/walk-in exactly (validated server-side against these strings).
const ITEM_CATEGORIES = [
  { value: 'laptop_tablet', label: 'Laptop / Tablet' },
  { value: 'mobile_phone', label: 'Mobile Phone' },
  { value: 'camera_recording_device', label: 'Camera / Recording Device' },
  { value: 'usb_drive_storage', label: 'USB Drive / External Storage' },
  { value: 'tools_equipment', label: 'Tools / Equipment' },
  { value: 'food_beverages', label: 'Food / Beverages' },
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
