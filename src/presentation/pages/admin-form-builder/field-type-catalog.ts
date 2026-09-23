import {
  AlignLeftIcon,
  CalendarIcon,
  ChevronDownIcon,
  ClockIcon,
  FileTextIcon,
  GridIcon,
  HashIcon,
  ListChecksIcon,
  MailIcon,
  PenToolIcon,
  PhoneIcon,
  ToggleLeftIcon,
  UploadIcon,
} from '../../components/icons'
import type { FormFieldType } from '../../../domain/entities/form-builder-schema'

export const OPTION_REQUIRED_FIELD_TYPES: readonly FormFieldType[] = ['dropdown_select', 'checkbox_list']

export interface FieldTypeMeta {
  type: FormFieldType
  label: string
  icon: typeof MailIcon | 'text-glyph'
}

export const FIELD_TYPE_CATALOG: FieldTypeMeta[] = [
  { type: 'text', label: 'Text Input', icon: 'text-glyph' },
  { type: 'email', label: 'Email Input', icon: MailIcon },
  { type: 'phone', label: 'Phone Input', icon: PhoneIcon },
  { type: 'number', label: 'Number Input', icon: HashIcon },
  { type: 'dropdown_select', label: 'Dropdown Select', icon: ChevronDownIcon },
  { type: 'date_picker', label: 'Date Picker', icon: CalendarIcon },
  { type: 'time_picker', label: 'Time Picker', icon: ClockIcon },
  { type: 'toggle_switch', label: 'Toggle / Switch', icon: ToggleLeftIcon },
  { type: 'checkbox_list', label: 'Checkbox List', icon: ListChecksIcon },
  { type: 'file_upload', label: 'File Upload', icon: UploadIcon },
  { type: 'textarea', label: 'Textarea', icon: AlignLeftIcon },
  { type: 'dynamic_table', label: 'Dynamic Table', icon: GridIcon },
  { type: 'rich_text_block', label: 'Rich Text Block', icon: FileTextIcon },
  { type: 'signature_pad', label: 'Signature Pad', icon: PenToolIcon },
  { type: 'static_text', label: 'Static Text', icon: AlignLeftIcon },
]

/** Field types that render as display-only content with no input control
 * and no submitted answer — see `DynamicField.tsx`'s `static_text` branch. */
export const CONTENT_ONLY_FIELD_TYPES: readonly FormFieldType[] = ['static_text']

export function fieldTypeLabel(type: FormFieldType): string {
  return FIELD_TYPE_CATALOG.find((entry) => entry.type === type)?.label ?? type
}

/**
 * System-seeded field keys whose value is consumed elsewhere in the
 * backend as a specific structured type, not just rendered as form
 * input — mirrors `_TYPE_LOCKED_SYSTEM_FIELD_KEYS`
 * (`src/vmss_api/form_builder/service.py`). Their Field Type control
 * stays disabled regardless of lock state. Every other system field's
 * type is editable once unlocked (locked fields) or directly (toggleable
 * fields), the same as an admin-authored field's other properties.
 */
export const TYPE_LOCKED_SYSTEM_FIELD_KEYS: ReadonlySet<string> = new Set([
  'registration_type',
  'email',
  'phone',
  'preferred_contact_method',
  'visitor_category',
  'id_proof_upload',
  'profile_photo',
  'preferred_visit_date',
  'preferred_visit_time',
])

const TYPE_LOCKED_FIELD_REASONS: Record<string, string> = {
  email: "This field's value must stay a valid, deliverable email address for notifications to reach the visitor.",
  phone: "This field's value must stay a valid phone number for notifications to reach the visitor.",
  preferred_contact_method: 'This field determines which contact channel notifications are sent through.',
  registration_type: 'This field determines how the invitation is processed and filtered.',
  preferred_visit_date: "This field's value is used as a real date for overstay detection and the emergency report.",
  preferred_visit_time: "This field's value is used as a real time for overstay detection and the emergency report.",
  id_proof_upload: "This field's value is a stored file, not form input.",
  profile_photo: "This field's value is a stored file, not form input.",
  visitor_category: "This field's options come from the Visitor Categories catalog, not this list.",
}

/** Field-specific reason shown under a disabled Field Type control — see
 * `TYPE_LOCKED_SYSTEM_FIELD_KEYS`. Falls back to a generic message for
 * any key not in the explicit map, though every current entry in that
 * set has one. */
export function typeLockedFieldReason(key: string): string {
  return TYPE_LOCKED_FIELD_REASONS[key] ?? "This field's type can't be changed."
}
