import { useEffect, useState } from 'react'
import { useAppDependencies } from '../context/app-dependencies-context'
import type { EffectiveFormFieldGroup, EffectiveFormStep, FormField } from '../../domain/entities/form-builder-schema'

/** Fetches the calling branch's currently *published* Form Builder
 * configuration (`GET /form-builder/effective` — no permission gate, safe
 * for the public visitor-facing wizard) once per `branchId` change, falling
 * back to the tenant-wide default when `branchId` is `undefined` (matches
 * `form_builder/service.py::resolve_effective_form`'s own fallback chain).
 * Used by both registration wizards to drive which steps exist/their order
 * (`activeSteps`, `findStepFields`) as well as the config-driven step
 * components (`ConsentStep`, `CarriedItemsStep`) for their field sets.
 */
export function useEffectiveForm(branchId: string | undefined): {
  steps: EffectiveFormStep[]
  isLoading: boolean
  error: boolean
} {
  const { getEffectiveFormUseCase } = useAppDependencies()
  const [steps, setSteps] = useState<EffectiveFormStep[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(false)
    getEffectiveFormUseCase
      .execute(branchId)
      .then((result) => {
        if (!cancelled) {
          setSteps(result)
          setIsLoading(false)
        }
      })
      .catch(() => {
        // Surfaced as `error` rather than silently resolving to an empty
        // step list, so callers can show a retry state instead of a
        // possibly-wrong default form (see design.md Decision 5).
        if (!cancelled) {
          setError(true)
          setIsLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [branchId, getEffectiveFormUseCase])

  return { steps, isLoading, error }
}

export function findStepFields(steps: EffectiveFormStep[], stepKey: string): FormField[] {
  return steps.find((step) => step.key === stepKey)?.fields ?? []
}

/** A step's admin-defined field groups (add-repeatable-field-groups /
 * add-conditional-field-groups) — used alongside `findStepFields` by any
 * step, built-in or custom, that renders its own groups (see
 * `FieldGroupsSection`). */
export function findStepGroups(steps: EffectiveFormStep[], stepKey: string): EffectiveFormFieldGroup[] {
  return steps.find((step) => step.key === stepKey)?.groups ?? []
}

/** A single toggleable field's active/required state, per its presence in
 * the effective form. `publish()`'s snapshot already excludes inactive
 * fields entirely (`form_builder/service.py`), so "absent" and "inactive"
 * are the same fact — mirrors how `form_builder/validation.py::is_field_required`
 * reads it server-side.
 */
export function findField(steps: EffectiveFormStep[], stepKey: string, fieldKey: string): FormField | undefined {
  return findStepFields(steps, stepKey).find((field) => field.key === fieldKey)
}
