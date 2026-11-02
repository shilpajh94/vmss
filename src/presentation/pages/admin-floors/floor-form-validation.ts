import type { FloorInput } from '../../../domain/entities/floor-schema'
import { wholeNumberRangeError } from '../../utils/whole-number-range'

// `FloorCreate`'s limits in the API. Floor 0 is the ground floor and
// negatives are basements, so both are valid floor numbers; a capacity of 0
// is what the API reports for "not set".
export const FLOOR_LIMITS = {
  name: 255,
  floorNumberMin: -20,
  floorNumberMax: 200,
  capacityMax: 100_000,
} as const

// The editable numbers can be momentarily empty while being retyped.
export type FloorNumberDrafts = { floorNumber: number | undefined; capacity: number | undefined }

export type FloorNumberErrors = Partial<Record<keyof FloorNumberDrafts, string>>

export function validateFloorNumbers(values: FloorNumberDrafts): FloorNumberErrors {
  const errors: FloorNumberErrors = {}
  const floorNumber = wholeNumberRangeError(values.floorNumber, {
    label: 'Floor number',
    min: FLOOR_LIMITS.floorNumberMin,
    max: FLOOR_LIMITS.floorNumberMax,
    required: true,
  })
  const capacity = wholeNumberRangeError(values.capacity, { label: 'Capacity', min: 0, max: FLOOR_LIMITS.capacityMax })
  if (floorNumber) errors.floorNumber = floorNumber
  if (capacity) errors.capacity = capacity
  return errors
}

// Only call once `validateFloorNumbers` passed: an empty capacity is sent as 0.
export function toFloorNumbers(values: FloorNumberDrafts): Pick<FloorInput, 'floorNumber' | 'capacity'> {
  return { floorNumber: values.floorNumber ?? 0, capacity: values.capacity ?? 0 }
}
