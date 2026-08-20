import z from "zod"

export const FloorSchema = z.object({
  id: z.string().min(1),
  buildingId: z.string().min(1),
  name: z.string().min(1),
  floorNumber: z.number(),
  isActive: z.boolean(),
  capacity: z.number().default(0),
  capacityType: z.enum(["guests", "staff"]).default("guests"),
  accessLevel: z.enum(["public", "restricted", "secure"]).default("public"),
})

export type Floor = z.infer<typeof FloorSchema>

export type FloorInput = Omit<Floor, "id">
