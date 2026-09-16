import z from "zod"

export const VehicleSchema = z.object({
  vehicleType: z.enum(["2_wheeler", "4_wheeler", "heavy"]),
  licensePlate: z.string().min(1),
  makeModel: z.string().min(1),
  color: z.string().min(1),
  // This vehicle's own answers for any admin-authored Vehicle Info field
  // beyond the locked license-plate field (add-generic-custom-field-support).
  customFieldValues: z.record(z.string(), z.unknown()).optional(),
})

export type Vehicle = z.infer<typeof VehicleSchema>
