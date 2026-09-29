import z from "zod"

// Doesn't carry its own `customFields` — every Vehicle Info answer flows
// through the request's single top-level `customFields` array instead, see
// visitor-schema.ts's matching comment.
export const VehicleSchema = z.object({
  // Plain string, not a fixed enum (make-id-proof-and-vehicle-type-
  // configurable): a valid value is whatever the calling branch's
  // published Vehicle Info "Vehicle Type" field currently declares as an
  // option.
  vehicleType: z.string().min(1),
  licensePlate: z.string().min(1),
  makeModel: z.string().min(1),
  color: z.string().min(1),
})

export type Vehicle = z.infer<typeof VehicleSchema>
