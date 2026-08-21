import z from "zod"

export const VehicleSchema = z.object({
  vehicleType: z.enum(["2_wheeler", "4_wheeler", "heavy"]),
  licensePlate: z.string().min(1),
  makeModel: z.string().min(1),
  color: z.string().min(1),
})

export type Vehicle = z.infer<typeof VehicleSchema>
