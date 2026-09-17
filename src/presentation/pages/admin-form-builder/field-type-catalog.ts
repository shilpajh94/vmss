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
]

export function fieldTypeLabel(type: FormFieldType): string {
  return FIELD_TYPE_CATALOG.find((entry) => entry.type === type)?.label ?? type
}
