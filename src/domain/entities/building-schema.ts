import z from "zod"

export const CheckpointSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
})

export type Checkpoint = z.infer<typeof CheckpointSchema>

export const FloorSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  checkpoints: z.array(CheckpointSchema),
  capacityCount: z.number().default(0),
  capacityUnit: z.enum(["Guests", "Staff"]).default("Guests"),
  accessLevel: z.enum(["public", "restricted", "secure"]).default("public"),
  departmentIds: z.array(z.string()).default([]),
  status: z.enum(["active", "inactive"]).default("active"),
})

export type Floor = z.infer<typeof FloorSchema>

export const BuildingSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  branchId: z.string().min(1),
  branchName: z.string().min(1),
  streetAddress: z.string().optional(),
  status: z.enum(["active", "inactive"]),
  receptionDesks: z.string().optional(),
  floors: z.array(FloorSchema),
})

export type Building = z.infer<typeof BuildingSchema>

export const BuildingInputSchema = BuildingSchema.pick({
  name: true,
  branchId: true,
  streetAddress: true,
  status: true,
  floors: true,
})

export type BuildingInput = z.infer<typeof BuildingInputSchema>
