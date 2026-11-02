// The inline error for a whole-number field the API bounds (`ge`/`le`), or
// undefined when the value is acceptable. `undefined` is "left empty".
export function wholeNumberRangeError(
  value: number | undefined,
  { min, max, label, required = false }: { min: number; max?: number; label: string; required?: boolean },
): string | undefined {
  if (value === undefined) return required ? `${label} is required.` : undefined
  if (!Number.isInteger(value)) return `${label} must be a whole number.`
  if (value < min) return max === undefined ? `${label} must be at least ${min}.` : `${label} must be between ${min} and ${max}.`
  if (max !== undefined && value > max) return `${label} must be between ${min} and ${max}.`
  return undefined
}
