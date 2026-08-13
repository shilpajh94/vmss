import z from "zod"

export const VehicleSchema = z.object({
  vehicleType: z.enum(["2-wheeler", "4-wheeler", "heavy"]),
  licensePlate: z.string().min(1),
  makeModel: z.string().min(1),
  color: z.string().min(1),
})

export type Vehicle = z.infer<typeof VehicleSchema>
