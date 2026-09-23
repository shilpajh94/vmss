import z from "zod"

export const VehicleSchema = z.object({
  // Plain string, not a fixed enum (make-id-proof-and-vehicle-type-
  // configurable): a valid value is whatever the calling branch's
  // published Vehicle Info "Vehicle Type" field currently declares as an
  // option.
  vehicleType: z.string().min(1),
  licensePlate: z.string().min(1),
  makeModel: z.string().min(1),
  color: z.string().min(1),
  // This vehicle's own answers for any admin-authored Vehicle Info field
  // beyond the locked license-plate field (add-generic-custom-field-support).
  customFieldValues: z.record(z.string(), z.unknown()).optional(),
})

export type Vehicle = z.infer<typeof VehicleSchema>
