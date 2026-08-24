import z from "zod"

export const SecurityGateSchema = z.object({
  id: z.string().min(1),
  buildingId: z.string().min(1),
  buildingName: z.string(),
  name: z.string().min(1),
  code: z.string().min(1),
  gateType: z.enum(["entry", "exit", "both"]).default("both"),
  highSecurity: z.boolean().default(false),
  authMethod: z.string().optional(),
  connectivityStatus: z.enum(["online", "maintenance", "offline"]).default("online"),
})

export type SecurityGate = z.infer<typeof SecurityGateSchema>

export type SecurityGateInput = Omit<SecurityGate, "id" | "buildingName" | "floorName">
