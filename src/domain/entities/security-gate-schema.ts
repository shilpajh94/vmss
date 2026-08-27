import z from "zod"

export const SecurityGateSchema = z.object({
  id: z.string().min(1),
  buildingId: z.string().min(1),
  buildingName: z.string(),
  name: z.string().min(1),
  code: z.string().min(1),
  gateType: z.enum(["entry", "exit", "both"]).default("both"),
  highSecurity: z.boolean().default(false),
})

export type SecurityGate = z.infer<typeof SecurityGateSchema>

export type SecurityGateInput = Omit<SecurityGate, "id" | "buildingName" | "floorName">
