import {
  AlertTriangleIcon,
  BriefcaseIcon,
  BuildingIcon,
  CalendarIcon,
  CameraIcon,
  CarIcon,
  CheckIcon,
  ClipboardListIcon,
  ClockIcon,
  FileSignatureIcon,
  FileTextIcon,
  HeartPulseIcon,
  IdCardIcon,
  LaptopIcon,
  MapPinIcon,
  PackageIcon,
  PhoneIcon,
  ShieldIcon,
  UserIcon,
  UsersIcon,
} from '../../components/icons'

type StepIcon = typeof UserIcon

/** One glyph per slug in the API's step-icon vocabulary (VMSS_API
 * `docs/features/form_builder.md`, "Step icons"). The API always assigns a
 * slug from that list; a slug added there needs an entry here, and anything
 * unrecognised renders the neutral default rather than a misleading glyph.
 */
const STEP_ICONS: Record<string, StepIcon> = {
  user: UserIcon,
  calendar: CalendarIcon,
  briefcase: BriefcaseIcon,
  package: PackageIcon,
  car: CarIcon,
  'shield-check': ShieldIcon,
  'check-circle': CheckIcon,
  'file-text': FileTextIcon,
  'file-signature': FileSignatureIcon,
  'id-card': IdCardIcon,
  camera: CameraIcon,
  'heart-pulse': HeartPulseIcon,
  laptop: LaptopIcon,
  phone: PhoneIcon,
  building: BuildingIcon,
  users: UsersIcon,
  clock: ClockIcon,
  'map-pin': MapPinIcon,
  'alert-triangle': AlertTriangleIcon,
  'clipboard-list': ClipboardListIcon,
}

export function stepIconFor(slug: string | null): StepIcon {
  return (slug && STEP_ICONS[slug]) || ClipboardListIcon
}
