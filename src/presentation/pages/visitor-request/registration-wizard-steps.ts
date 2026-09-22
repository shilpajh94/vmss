import { prettifyKey } from '../../utils/prettify-key'
import type { EffectiveFormStep } from '../../../domain/entities/form-builder-schema'

// Matches `VMSS_API/src/vmss_api/form_builder/defaults.py`'s seeded step
// keys. Shared by both the visitor-request and staff-visitor-registration
// wizards so a step's key resolves to the same built-in component/label in
// either wizard — see design.md (fix-wizard-inactive-steps) Decision 1.
export type StepKey = 'visitor_info' | 'visit_details' | 'carried_items' | 'vehicle_info' | 'consent_agreement' | 'review_confirm'

const CANONICAL_STEP_LABELS: Record<StepKey, string> = {
  visitor_info: 'Visitor Info',
  visit_details: 'Visit Info',
  carried_items: 'Carried Items',
  vehicle_info: 'Vehicle Info',
  consent_agreement: 'Consent Agreement',
  review_confirm: 'Review & Confirm',
}

const CANONICAL_STEP_ORDER: StepKey[] = [
  'visitor_info',
  'visit_details',
  'carried_items',
  'vehicle_info',
  'consent_agreement',
  'review_confirm',
]

const CANONICAL_STEP_KEYS = new Set<string>(CANONICAL_STEP_ORDER)

export function isCanonicalStepKey(key: string): key is StepKey {
  return CANONICAL_STEP_KEYS.has(key)
}

/** A step's display label: the admin-configured `name` if set, otherwise
 * the historical built-in label for a canonical step, otherwise a
 * prettified version of the key (for a custom step with no name).
 */
export function resolveStepLabel(step: EffectiveFormStep): string {
  if (step.name) return step.name
  if (isCanonicalStepKey(step.key)) return CANONICAL_STEP_LABELS[step.key]
  return prettifyKey(step.key)
}

/** Placeholder step labels shown while the effective config is still
 * loading, so the sidebar/stepper doesn't flash from a full list to a
 * shorter one once the real (possibly filtered) list resolves.
 */
export function getSkeletonStepLabels(): string[] {
  return CANONICAL_STEP_ORDER.map((key) => CANONICAL_STEP_LABELS[key])
}

/** Active steps from the effective config, in their configured order —
 * what both wizards' sidebar/stepper and step-content routing render from,
 * instead of a hardcoded list of all six canonical steps.
 */
export function getActiveSteps(steps: EffectiveFormStep[]): EffectiveFormStep[] {
  return [...steps].filter((step) => step.isActive).sort((a, b) => a.orderIndex - b.orderIndex)
}
